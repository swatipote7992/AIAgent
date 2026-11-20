import logging
import os
from functools import lru_cache
from pathlib import PureWindowsPath

from dotenv import load_dotenv
from langchain_core.callbacks import get_usage_metadata_callback
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from openai import ContentFilterFinishReasonError, LengthFinishReasonError
from pydantic import BaseModel, Field, ValidationError
from retrieval.retrieval import get_retriever
from backend.guadrails.input_guardrails import input_guardrails
from observability.tracing import traced
from data.prompts import load_continue_prompt, load_system_prompt
from opentelemetry import trace
from utility.continuation_handler import AnswerBlockedError, AnswerTruncatedError, blocked_message, continue_reply
from utility.finish_reason_handler import FinishReasonHandler
from utility.timeout_handler import clamp_timeout
from utility.transient_error_checker import is_transient

# .env wins over variables already set in the shell
load_dotenv(override=True)

log = logging.getLogger("chain_llm")


class Reply(BaseModel):
    # What the chat model returns: the answer plus questions the user could ask next.

    answer: str = Field(description="The answer, with source and page for each fact.")
    followups: list[str] = Field(
        description="Up to 3 short follow-up questions, each complete on its own and answerable from the context."
    )


@lru_cache
def get_cached_retriever():
    return get_retriever()


@traced("retrieval")
def retrieve_chunks(question: str):
    # Find the chunks relevant to the question in Azure AI Search. Embedding the question and the search each have
    # their own timeout and retries in their SDK clients (see vector_store.py and embeddings.py); nothing retries here.
    chunks = get_cached_retriever().invoke(question)
    # Only a count and the policy file names go on the span, never the chunk text.
    # The stored source can be a full local path, so keep just the file name.
    span = trace.get_current_span()
    span.set_attribute("rag.chunks", len(chunks))
    span.set_attribute(
        "rag.sources",
        sorted({PureWindowsPath(str(c.metadata.get("source"))).name for c in chunks}),
    )
    return chunks


@traced("prompt")
def build_prompt(chunks):
    # Join the chunk texts into one context string, keeping source and page for citations
    context = "\n\n".join(
        f"[{c.metadata.get('source')}, page {c.metadata.get('page_label')}]\n{c.page_content}"
        for c in chunks
    )

    # The system prompt lives in backend/data/prompts/sys_prompt_v<N>.py
    system_text, version = load_system_prompt()
    trace.get_current_span().set_attribute("prompt.version", version)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_text),
        ("human", "{question}"),
    ])
    return prompt, context


def build_llm(deployment: str) -> AzureChatOpenAI:
    # The chat model for one deployment, built for every question from the settings in .env.
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "1000"))
    trace.get_current_span().set_attribute("gen_ai.request.max_tokens", max_tokens)
    return AzureChatOpenAI(
        azure_deployment=deployment,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        temperature=0,
        timeout=clamp_timeout(float(os.environ.get("LLM_TIMEOUT_SECONDS", "25"))),
        max_retries=int(os.environ.get("LLM_MAX_RETRIES", "1")),
    )


def record_llm_attributes(llm, usage, cut_input: int, cut_output: int) -> None:
    # Names and token counts only, never any text. The standard OpenTelemetry GenAI names, so tools such as
    # Microsoft Foundry's Traces page can recognise the call.
    span = trace.get_current_span()
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.provider.name", "azure.ai.openai")
    span.set_attribute("gen_ai.request.model", llm.deployment_name)
    span.set_attribute(
        "gen_ai.usage.input_tokens",
        cut_input
        + sum(s.get("input_tokens", 0) for s in usage.usage_metadata.values()),
    )
    span.set_attribute(
        "gen_ai.usage.output_tokens",
        cut_output
        + sum(s.get("output_tokens", 0) for s in usage.usage_metadata.values()),
    )


def invoke_with_continuation(
    llm, prompt, context: str, question: str, handler
) -> tuple[Reply, int, int]:
    # Ask the model for the structured reply. If the token limit cuts it, send the partial text back as an AI message
    # and ask the model to carry on, at most MAX_CONTINUATIONS times (see utility/continuation_handler.py).
    # Returns the reply plus the input and output tokens of the call that was cut (the library raises, so the
    # usage callback never sees them); both are 0 when nothing was cut.
    inputs = {"context": context, "question": question}
    try:
        reply = (prompt | llm.with_structured_output(Reply)).invoke(
            inputs, config={"callbacks": [handler]}
        )
        return reply, 0, 0
    except ContentFilterFinishReasonError as blocked:
        # The handler has already recorded "content_filter" (on_llm_error); turn it into a clear error.
        raise AnswerBlockedError(blocked_message("content_filter")) from blocked
    except LengthFinishReasonError as cut:
        # The handler has already recorded "length" (on_llm_error).
        usage = cut.completion.usage
        partial = cut.completion.choices[0].message.content or ""
        # The instruction lives in backend/data/prompts/continue_prompt_v<N>.py
        instruction, version = load_continue_prompt()
        trace.get_current_span().set_attribute("continue_prompt.version", version)
        text, _ = continue_reply(
            llm,
            prompt.format_messages(**inputs),
            partial,
            instruction,
            handler,
        )
        try:
            reply = Reply.model_validate_json(text.strip())
        except ValidationError as error:
            raise AnswerTruncatedError(
                "The continued answer could not be joined into a valid reply."
            ) from error
        return (
            reply,
            (usage.prompt_tokens if usage else 0),
            (usage.completion_tokens if usage else 0),
        )


def invoke_with_fallback(prompt, context: str, question: str, handler):
    # Answer with the primary chat deployment. If it keeps failing with a transient error (after the client's own
    # retries), answer with the fallback deployment, if AZURE_OPENAI_CHAT_FALLBACK_DEPLOYMENT is set.
    # Returns the reply, the tokens of a cut-off call, and the model that answered.
    deployments = [os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini")]
    fallback = os.environ.get("AZURE_OPENAI_CHAT_FALLBACK_DEPLOYMENT", "").strip()
    if fallback:
        deployments.append(fallback)
    for index, deployment in enumerate(deployments):
        llm = build_llm(deployment)
        try:
            reply, cut_input, cut_output = invoke_with_continuation(llm, prompt, context, question, handler)
            return reply, cut_input, cut_output, llm
        except Exception as error:
            if index == len(deployments) - 1 or not is_transient(error):
                raise
            log.warning("chat deployment failed (%s), using the fallback deployment", type(error).__name__)
            trace.get_current_span().set_attribute("llm.fallback_used", True)


@traced("llm_generation")
def generate_reply(prompt, context: str, question: str) -> Reply:
    handler = FinishReasonHandler()  # puts the finish reason of each model call on the span
    # The callback counts the tokens of every call that returns normally.
    with get_usage_metadata_callback() as usage:
        reply, cut_input, cut_output, llm = invoke_with_fallback(prompt, context, question, handler)
    record_llm_attributes(llm, usage, cut_input, cut_output)
    return reply


@traced("ask_llm")
def ask_llm(question: str) -> dict:
    # Retrieve the chunks relevant to the question and let the chat model answer from them.
    # Only the length of the question goes on the span, never its text.
    trace.get_current_span().set_attribute("question.chars", len(question))
    input_guardrails(question)
    chunks = retrieve_chunks(question)
    prompt, context = build_prompt(chunks)
    reply = generate_reply(prompt, context, question)

    return {
        "answer": reply.answer,
        "followups": reply.followups[:3],
        "chunks": [
            {
                "source": c.metadata.get("source"),
                "page": c.metadata.get("page_label"),
                "title": c.page_content.splitlines()[0] if c.page_content else "",
                "text": c.page_content,
            }
            for c in chunks
        ],
    }
