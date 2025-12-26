Goal: A handrolled agent in python

using anthropic api. just the response api.

- tool calls
- loop
- structured outputs via pydantic(?)

how it will work:
take in prompt
pass in tools for the agent to use (these get included into the system prompt)
loop:
    call llm response api, get response
    response may be a request to call tools - if so, call the requested tool with the data provided by the llm response
    append the llm response and tool calls to the conversation history
    if the toolcall is the "output" tool, return the response break loop
return final response
