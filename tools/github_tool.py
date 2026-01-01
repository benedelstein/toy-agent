import subprocess
from pydantic import BaseModel
from tools.tool import Tool
from events import EventEmitter


class CreatePullRequestInput(BaseModel):
    title: str
    description: str
    base: str
    draft: bool = False


class CreatePullRequestOutput(BaseModel):
    url: str


def create_pull_request(input: CreatePullRequestInput) -> CreatePullRequestOutput:
    # gh pr create --title <title> --body <description> --base <base>
    # if draft is true, add --draft
    command = ["gh", "pr", "create", "--title", input.title, "--body", input.description, "--base", input.base]
    if input.draft:
        command.append("--draft")
    subprocess.run(command)
    output = subprocess.run(command, capture_output=True, text=True)
    if output.returncode != 0:
        raise Exception(f"Failed to create pull request: {output.stderr}")
    url = output.stdout.strip()
    return CreatePullRequestOutput(url=url)


def create_pull_request_tool(emitter: EventEmitter) -> Tool:
    return Tool(
        tool_name="create_pull_request",
        description="""Create a pull request on Github. Call this tool when you are ready to create a pr to merge your changes into the main branch.
        After you have completed a feature, call this tool to start getting your changes reviewed and merged.
        """,
        input_schema=CreatePullRequestInput,
        output_schema=CreatePullRequestOutput,
        run=create_pull_request,
        emitter=emitter
    )
