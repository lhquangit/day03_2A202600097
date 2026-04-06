import argparse
import json
import os
from typing import Optional

from dotenv import load_dotenv

from src.agent.agent import ReActAgent
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.tools import get_agent_tools


def build_provider_from_env() -> LLMProvider:
    load_dotenv()

    provider_name = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    default_model = os.getenv("DEFAULT_MODEL", "gpt-4o")

    if provider_name == "openai":
        from src.core.openai_provider import OpenAIProvider

        return OpenAIProvider(
            model_name=default_model,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    if provider_name in {"google", "gemini"}:
        from src.core.gemini_provider import GeminiProvider

        return GeminiProvider(
            model_name=default_model or "gemini-1.5-flash",
            api_key=os.getenv("GEMINI_API_KEY"),
        )
    if provider_name == "local":
        from src.core.local_provider import LocalProvider

        model_path = os.getenv("LOCAL_MODEL_PATH", "")
        if not model_path:
            raise ValueError("LOCAL_MODEL_PATH is required when DEFAULT_PROVIDER=local.")
        return LocalProvider(model_path=model_path)

    raise ValueError(
        f"Unsupported DEFAULT_PROVIDER `{provider_name}`. Use openai, google, gemini, or local."
    )


def run_agent_session(
    prompt: str,
    *,
    llm: Optional[LLMProvider] = None,
    max_steps: int = 5,
    log_path: Optional[str] = None,
) -> tuple[str, str, str]:
    provider = llm or build_provider_from_env()
    agent = ReActAgent(llm=provider, tools=get_agent_tools(), max_steps=max_steps)
    target_log_path = log_path or logger.create_run_log_path(prefix="agent_run")
    target_json_path = logger.create_run_log_path(prefix="agent_answer", extension="json")
    target_txt_path = logger.create_run_log_path(prefix="agent_answer", extension="txt")

    with logger.capture_console(target_log_path) as captured_log_path:
        print(f"Run log file: {captured_log_path}")
        print(f"User Prompt: {prompt}")
        artifact_payload = {
            "status": "success",
            "prompt": prompt,
            "provider": provider.__class__.__name__,
            "model": provider.model_name,
            "max_steps": max_steps,
            "final_answer": "",
            "history": [],
            "text_log_path": captured_log_path,
            "final_answer_text_path": target_txt_path,
        }
        try:
            final_answer = agent.run(prompt)
            artifact_payload["final_answer"] = final_answer
            artifact_payload["history"] = agent.history
            print("\n=== final_answer ===")
            print(final_answer)
        except Exception as exc:
            artifact_payload["status"] = "error"
            artifact_payload["error"] = {
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
            artifact_payload["history"] = agent.history
            raise
        finally:
            final_answer_text = artifact_payload["final_answer"]
            if artifact_payload["status"] == "error":
                error = artifact_payload.get("error", {})
                final_answer_text = (
                    "Agent run failed.\n"
                    f"Error Type: {error.get('type', 'Unknown')}\n"
                    f"Message: {error.get('message', 'No message provided.')}\n"
                )
            txt_log_path = logger.write_text_artifact(
                final_answer_text,
                path=target_txt_path,
                prefix="agent_answer",
            )
            artifact_payload["final_answer_text_path"] = txt_log_path
            json_log_path = logger.write_json_artifact(
                artifact_payload,
                path=target_json_path,
                prefix="agent_answer",
            )
            logger.log_event(
                "AGENT_RESULT_JSON",
                {
                    "json_path": json_log_path,
                    "status": artifact_payload["status"],
                },
            )
            print(f"Agent answer JSON: {json_log_path}")
            print(f"Agent answer TXT: {txt_log_path}")

    return final_answer, target_log_path, target_json_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the School Nutrition ReAct agent.")
    parser.add_argument(
        "--prompt",
        type=str,
        help="Prompt to send to the agent. If omitted, the script will ask interactively.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=5,
        help="Maximum number of ReAct steps before the agent stops.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prompt = args.prompt or input("Prompt: ").strip()
    if not prompt:
        raise ValueError("A non-empty prompt is required.")
    run_agent_session(prompt, max_steps=args.max_steps)


if __name__ == "__main__":
    main()
