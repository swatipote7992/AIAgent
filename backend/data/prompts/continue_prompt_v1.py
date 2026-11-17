# Version 1 of the instruction sent after a reply that the token limit cut off (see utility/continuation.py).
# The partial reply goes back to the model as an AI message, then this text as the next user message.
# The reply is a JSON object (answer and followups), so the rest of it must join the partial text exactly.
CONTINUE_PROMPT = (
    "Your previous reply was cut off because it reached the length limit. It is a JSON object. "
    "Carry on from the exact character where it stopped. Do not repeat anything you already wrote, "
    "do not start again, and do not add any explanation or code fence. Output only the remaining text."
)
