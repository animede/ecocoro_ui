import argparse
import os


def parse_args():
    parser = argparse.ArgumentParser(description="ecocoro image generation server")
    parser.add_argument(
        "--llm-endpoint",
        required=True,
        help="OpenAI互換LLMサーバーのベースURL (例: http://39.110.248.77:64650/v1)",
    )
    parser.add_argument("--llm-model", default="default", help="LLMモデル名")
    parser.add_argument("--llm-api-key", default="EMPTY", help="LLM APIキー")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model-id", default="alfredplpl/ecocoro-preview-1", help="拡散モデルのHugging Face ID")
    parser.add_argument("--outputs-dir", default="./outputs", help="生成画像・メタデータの保存先")
    parser.add_argument("--device", default="cuda")
    return parser.parse_args()


def main():
    args = parse_args()

    os.environ["ECOCORO_LLM_ENDPOINT"] = args.llm_endpoint
    os.environ["ECOCORO_LLM_MODEL"] = args.llm_model
    os.environ["ECOCORO_LLM_API_KEY"] = args.llm_api_key
    os.environ["ECOCORO_MODEL_ID"] = args.model_id
    os.environ["ECOCORO_OUTPUTS_DIR"] = args.outputs_dir
    os.environ["ECOCORO_DEVICE"] = args.device

    import uvicorn

    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
