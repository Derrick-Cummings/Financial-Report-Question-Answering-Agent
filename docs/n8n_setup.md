
# V1 n8n Technical Setup

## Project and Platform

- n8n project name: Financial Report Question Answering Agent
- n8n version: 2.47.6
- MCP status: Not used by the V1 FinQA workflow.

## V1 Workflow

- Workflow name: v1_finqa_solver
- Purpose: One Solver Agent answers FinQA questions using permitted evidence and a Calculator tool.

### 1. FinQA Task Webhook

- Trigger: FinQA Task Webhook using POST.
- Webhook input fields: task_id, question, pre_text, post_text, and table.
- Webhook response mode: Using Respond to Webhook Node.

### 2. Build Permitted Evidence

- Node: Build Permitted Evidence.
- Output field: solver_input.
- Mapping: Combines task_id, question, pre_text, post_text, and table from the incoming Webhook body.
- Evidence rule: The Solver uses only the supplied task question and permitted report evidence.

### 3. Solver Agent

- Node: Solver Agent.
- Role: Creates an executable arithmetic expression from permitted evidence, calls the Calculator tool, and returns a structured answer.
- Prompt location: prompts/v1/solver_prompt.md.
- Maximum iterations: 6.

#### Anthropic Chat Model

- Provider: Anthropic.
- Model identifier: claude-opus-5-5.
- Credential method: Anthropic API credential stored in n8n Credentials.
- Thinking mode: Adaptive.
- Reasoning effort: Not exposed by the n8n Anthropic Chat Model node.

#### Calculator Tool

- Tool: n8n built-in Calculator.
- Connection: Attached to the Solver Agent Tool connection.
- Purpose: Evaluates the Solver's arithmetic expression.
- Credential requirement: None.
- Rule: The Solver must call the Calculator before returning the final answer.

#### Structured Result Parser

- Node: Structured Result Parser.
- Required fields: task_id, arithmetic_expression, calculator_result, final_answer, evidence_used, and trace.

### 4. Respond with Result

- Node: Respond with Result.
- Response type: JSON.
- Response expression: {{ $json.output }}

## Workflow Export

- File: workflows/v1/v1_solver_workflow.json