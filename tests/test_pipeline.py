import json
import random
import shutil
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from google.genai import types

from shitpost import history, pipeline, script, video_web
from shitpost.config import CHANNELS_DIR, load_channel
from shitpost.publish import Post
from shitpost.video import VideoFiltered

PNG = b"\x89PNG\r\n\x1a\nfake"


def scenario(n=0):
    return script.Scenario(
        baslik=f"Title {n}",
        aciklama="caption",
        ozet=f"summary {n}",
        ilk_kare="first frame",
        video_prompt="video prompt",
        hashtagler=["funny"],
    )


class FakeClient:
    def __init__(self, filtered_times=0):
        self.filtered_times = filtered_times
        self.video_calls = []
        self.text_prompts = []
        self.models = NS(generate_content=self._generate_content, generate_videos=self._generate_videos)
        self.operations = NS(get=self._get_op)
        self.files = NS(download=self._download)

    def _generate_content(self, model, contents, config):
        if config.response_modalities == ["IMAGE"]:
            part = NS(inline_data=NS(data=PNG, mime_type="image/png"))
            return NS(candidates=[NS(content=NS(parts=[part]))], text=None)
        self.text_prompts.append(contents)
        s = scenario(len(self.text_prompts))
        return NS(parsed=s, text=s.model_dump_json())

    def _generate_videos(self, **kwargs):
        self.video_calls.append(kwargs)
        return NS(done=False, name="op", error=None, response=None)

    def _get_op(self, op):
        if self.filtered_times:
            self.filtered_times -= 1
            resp = NS(generated_videos=[], rai_media_filtered_reasons=["celebrity"])
        else:
            resp = NS(generated_videos=[NS(video=types.Video())], rai_media_filtered_reasons=None)
        return NS(done=True, name="op", error=None, response=resp)

    def _download(self, file):
        file.video_bytes = b"mp4data"


@pytest.fixture
def channel(tmp_path):
    shutil.copytree(CHANNELS_DIR / "spoderman", tmp_path / "kanallar" / "spoderman",
                    ignore=shutil.ignore_patterns("*.png", "gecmis.json"))
    return load_channel("spoderman", tmp_path / "kanallar")


@pytest.fixture
def api_channel(channel):
    channel.video["motor"] = "api"
    return channel


def run(client, channel, tmp_path, **kw):
    return pipeline.run(client, channel, out_root=tmp_path / "cikti", log=lambda *a: None,
                        sleep=lambda s: None, rng=random.Random(1), **kw)


def test_channel_config_loads(channel):
    assert [c.name for c in channel.characters] == ["Spoderman", "Orange"]
    assert channel.video["en_boy"] == "9:16"
    assert channel.video["motor"] == "gemini_web"
    assert set(channel.platforms) == {"youtube", "tiktok_web", "instagram_web"}


def test_pick_theme_skips_recent(channel):
    for t in channel.themes[:5]:
        history.add(channel.history_path, title="t", summary="s", theme=t, links={})
    for seed in range(30):
        assert script.pick_theme(channel, random.Random(seed)) not in channel.themes[:5]


def test_prompt_includes_theme_and_past(channel):
    prompt = script.build_prompt(channel, "on the moon", ["spoderman ate the orange"])
    assert "on the moon" in prompt
    assert "spoderman ate the orange" in prompt
    assert "Spoderman takes everything way too seriously." in prompt


def test_dry_run_creates_outputs_without_history(api_channel, tmp_path):
    client = FakeClient()
    result = run(client, api_channel, tmp_path, publish=False)

    assert result.video.read_bytes() == b"mp4data"
    assert (result.folder / "ilk_kare.png").read_bytes() == PNG
    assert json.loads((result.folder / "senaryo.json").read_text())["baslik"] == "Title 1"
    assert all(c.reference.exists() for c in api_channel.characters)
    cfg = client.video_calls[0]["config"]
    assert cfg.aspect_ratio == "9:16" and cfg.duration_seconds == 8
    assert client.video_calls[0]["image"].image_bytes == PNG
    assert not api_channel.history_path.exists()


def test_filtered_video_retries_with_new_scenario(api_channel, tmp_path):
    client = FakeClient(filtered_times=1)
    result = run(client, api_channel, tmp_path, publish=False)
    assert len(client.video_calls) == 2
    assert result.scenario.baslik == "Title 2"


def test_gives_up_after_attempts(api_channel, tmp_path):
    with pytest.raises(RuntimeError, match="video üretilemedi"):
        run(FakeClient(filtered_times=5), api_channel, tmp_path, publish=False, attempts=2)


def test_publish_records_history(api_channel, tmp_path, monkeypatch):
    posts = []

    def fake_publish_all(ch, video, post):
        posts.append(post)
        return {"youtube": "https://youtube.com/shorts/x"}, {"ayrshare": "boom"}

    monkeypatch.setattr(pipeline, "publish_all", fake_publish_all)
    result = run(FakeClient(), api_channel, tmp_path)

    assert result.errors == {"ayrshare": "boom"}
    assert posts[0].hashtags == api_channel.hashtags + ["funny"]
    entry = history.load(api_channel.history_path)[-1]
    assert entry["ozet"] == "summary 1" and entry["linkler"]["youtube"].endswith("/x")


def test_caption_with_tags():
    post = Post(title="t", caption="lol", hashtags=["shorts", "#meme"])
    assert post.caption_with_tags() == "lol\n\n#shorts #meme"


@pytest.fixture
def web_env(tmp_path, monkeypatch):
    from shitpost import accounts

    monkeypatch.setenv("GEMINI_PROFILLER", "P1;P2")
    monkeypatch.setenv("GEMINI_GUNLUK_LIMIT", "2")
    monkeypatch.setattr(accounts, "STATE_PATH", tmp_path / "yerel" / "kota.json")
    calls = []

    def fake_web(profile, prompt, out_path, log=print, **kw):
        calls.append((profile, prompt))
        behavior = web_env_behavior.pop(0) if web_env_behavior else "ok"
        if behavior == "quota":
            raise video_web.QuotaExceeded("daily limit")
        if behavior == "filtered":
            raise VideoFiltered("no")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"webvideo")
        return out_path

    web_env_behavior = []
    monkeypatch.setattr(video_web, "generate_video_web", fake_web)
    return NS(calls=calls, behavior=web_env_behavior, accounts=accounts)


def test_web_engine_uses_account_and_counts_quota(channel, tmp_path, web_env):
    result = run(FakeClient(), channel, tmp_path, publish=False)
    assert result.video.read_bytes() == b"webvideo"
    profile, prompt = web_env.calls[0]
    assert profile == "P1"
    assert "Vertical 9:16" in prompt and "bootleg" in prompt and "first frame" in prompt
    assert not any(c.reference.exists() for c in channel.characters)

    run(FakeClient(), channel, tmp_path, publish=False)
    assert web_env.accounts.available() == ["P2"]


def test_web_engine_switches_account_on_quota(channel, tmp_path, web_env):
    web_env.behavior.append("quota")
    run(FakeClient(), channel, tmp_path, publish=False)
    assert [c[0] for c in web_env.calls] == ["P1", "P2"]
    assert web_env.accounts.available() == ["P2"]


def test_web_engine_stops_when_all_quota_used(channel, tmp_path, web_env):
    web_env.behavior.extend(["quota", "quota"])
    with pytest.raises(pipeline.NoQuotaLeft):
        run(FakeClient(), channel, tmp_path, publish=False)
    with pytest.raises(pipeline.NoQuotaLeft):
        run(FakeClient(), channel, tmp_path, publish=False)
    assert len(web_env.calls) == 2


def test_web_engine_retries_filtered_with_new_scenario(channel, tmp_path, web_env):
    web_env.behavior.append("filtered")
    result = run(FakeClient(), channel, tmp_path, publish=False)
    assert result.scenario.baslik == "Title 2"
    assert [c[0] for c in web_env.calls] == ["P1", "P1"]


def test_scenario_falls_back_when_model_removed(channel):
    from google.genai import errors

    client = FakeClient()
    original = client.models.generate_content
    used = []

    def gen(model, contents, config):
        used.append(model)
        if model == channel.models["metin"]:
            raise errors.ClientError(404, {"error": {"code": 404, "message": "no longer available", "status": "NOT_FOUND"}})
        return original(model=model, contents=contents, config=config)

    client.models.generate_content = gen
    s = script.write_scenario(client, channel, "theme")
    assert used == [channel.models["metin"], script.FALLBACK_TEXT_MODELS[0]]
    assert s.baslik == "Title 1"


def test_scenario_retries_when_server_busy(channel, monkeypatch):
    from google.genai import errors

    monkeypatch.setattr(script, "_sleep", lambda s: None)
    client = FakeClient()
    original = client.models.generate_content
    used = []

    def gen(model, contents, config):
        used.append(model)
        if len(used) <= 2:
            raise errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
        return original(model=model, contents=contents, config=config)

    client.models.generate_content = gen
    assert script.write_scenario(client, channel, "theme").baslik == "Title 1"
    assert used == [channel.models["metin"], *script.FALLBACK_TEXT_MODELS[:2]]


def test_scenario_prompt_forbids_risky_content(channel):
    assert "explosions" in script.build_prompt(channel, "x", [])


def test_guncelle_overwrites_files_but_keeps_history(tmp_path, monkeypatch):
    import io
    import zipfile

    from shitpost import __main__ as cli
    from shitpost import config

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("video-gen-branch/", "")
        z.writestr("video-gen-branch/shitpost/new.py", "x = 1\n")
        z.writestr("video-gen-branch/kanallar/spoderman/gecmis.json", "[]")
    (tmp_path / "kanallar" / "spoderman").mkdir(parents=True)
    (tmp_path / "kanallar" / "spoderman" / "gecmis.json").write_text('[{"keep": 1}]')

    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr("requests.get", lambda url, timeout: NS(content=buf.getvalue(), raise_for_status=lambda: None))
    assert cli.main(["guncelle"]) == 0
    assert (tmp_path / "shitpost" / "new.py").read_text() == "x = 1\n"
    assert "keep" in (tmp_path / "kanallar" / "spoderman" / "gecmis.json").read_text()


def test_scenario_waits_only_when_all_models_busy(channel, monkeypatch):
    from google.genai import errors

    waits = []
    monkeypatch.setattr(script, "_sleep", waits.append)
    client = FakeClient()
    original = client.models.generate_content
    n_models = 1 + len(script.FALLBACK_TEXT_MODELS)
    calls = []

    def gen(model, contents, config):
        calls.append(model)
        if len(calls) <= n_models:
            raise errors.ServerError(503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}})
        return original(model=model, contents=contents, config=config)

    client.models.generate_content = gen
    script.write_scenario(client, channel, "theme")
    assert waits == [script.RETRY_DELAYS[0]]
