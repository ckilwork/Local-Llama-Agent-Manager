from app.models.server_config import ServerConfig
from app.services.command_builder import CommandBuilder


def test_build_arguments_contains_mvp_options() -> None:
    config = ServerConfig(
        model_path=r"D:\Models\test model.gguf",
        port=8081,
        context_length=131072,
        gpu_layers=99,
        flash_attention=True,
        jinja=True,
        reasoning_format="auto",
        parallel=2,
    )

    assert CommandBuilder.build_arguments(config) == [
        "-m", r"D:\Models\test model.gguf",
        "-c", "131072",
        "--port", "8081",
        "--gpu-layers", "99",
        "--parallel", "2",
        "--reasoning-format", "auto",
        "--flash-attn", "on",
        "--jinja",
    ]


def test_build_arguments_adds_mmproj_only_when_configured() -> None:
    config = ServerConfig(model_path="model.gguf", mmproj_path="vision-mmproj.gguf")
    args = CommandBuilder.build_arguments(config)
    assert args[args.index("--mmproj") + 1] == "vision-mmproj.gguf"


def test_mtp_draft_is_optional_and_visible_in_preview() -> None:
    plain = ServerConfig(model_path="model.gguf")
    assert "--spec-type" not in CommandBuilder.build_arguments(plain)
    assert "--model-draft" not in CommandBuilder.build_arguments(plain)

    draft = ServerConfig(model_path="model.gguf", mtp_path=r"D:\Models\mtp draft.gguf")
    arguments = CommandBuilder.build_arguments(draft)
    assert arguments[-4:] == [
        "--spec-type", "draft-mtp", "--model-draft", r"D:\Models\mtp draft.gguf"
    ]
    assert '--model-draft "D:\\Models\\mtp draft.gguf"' in CommandBuilder.build_command_preview(draft)
