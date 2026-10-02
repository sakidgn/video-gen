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
from shitpost.video import CopyrightFiltered, VideoFiltered

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


@pytest.fixture(autouse=True)
def _gemini_scenarios_by_default(request):
    if "channel" in request.fixturenames:
        request.getfixturevalue("channel").scenario["motor"] = "gemini_api"


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
    assert load_channel("spoderman", channel.dir.parent).scenario["motor"] == "chatgpt_web"
    assert set(channel.platforms) == {"youtube_web", "tiktok_web", "instagram_web"}


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
    calls = []

    def fake_web(profile, prompt, out_path, log=print, **kw):
        calls.append((profile, prompt))
        behavior = web_env_behavior.pop(0) if web_env_behavior else "ok"
        if behavior == "quota":
            raise video_web.QuotaExceeded("daily limit")
        if behavior == "filtered":
            raise VideoFiltered("no")
        if behavior == "copyright":
            raise CopyrightFiltered("telif")
        if behavior == "busy":
            raise video_web.GeminiBusy("full capacity")
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
    assert "Vertical 9:16" in prompt and "the costume guy" in prompt and "first frame" in prompt
    assert "spoderman" not in prompt.lower()
    assert not any(c.reference.exists() for c in channel.characters)

    run(FakeClient(), channel, tmp_path, publish=False)
    assert [c[0] for c in web_env.calls] == ["P1", "P1"]


def test_web_engine_switches_account_on_quota(channel, tmp_path, web_env):
    web_env.behavior.append("quota")
    run(FakeClient(), channel, tmp_path, publish=False)
    assert [c[0] for c in web_env.calls] == ["P1", "P2"]


def test_web_engine_stops_when_all_quota_used(channel, tmp_path, web_env):
    web_env.behavior.extend(["quota", "quota"])
    with pytest.raises(pipeline.NoQuotaLeft):
        run(FakeClient(), channel, tmp_path, publish=False)
    assert [c[0] for c in web_env.calls] == ["P1", "P2"]
    run(FakeClient(), channel, tmp_path, publish=False)
    assert [c[0] for c in web_env.calls] == ["P1", "P2", "P1"]


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


def test_aliases_replace_real_names_in_video_prompt(channel):
    s = script.Scenario(baslik="Spoderman pazarda", aciklama="a", ozet="o",
                        ilk_kare="SPODERMAN stands", video_prompt="Spoderman says hi", hashtagler=[])
    prompt = script.web_video_prompt(channel, s)
    assert "spoderman" not in prompt.lower()
    assert "Opening shot: the costume guy stands." in prompt


def test_chatgpt_scenario_engine(channel, monkeypatch):
    from shitpost import chatgpt_web

    channel.scenario["motor"] = "chatgpt_web"
    monkeypatch.setenv("CHATGPT_PROFILI", "P1")
    sent = []

    def fake_ask(profile, message, url, project, log, debug_dir):
        sent.append((profile, message, project))
        return "```\nPrompt: Spoderman slips a tomato into Orange's pocket and says 'Bu domates benim!' in a low-poly bazaar.\n```"

    monkeypatch.setattr(chatgpt_web, "ask", fake_ask)
    client = FakeClient()
    meta = script.Meta(baslik="Spoderman pazarda", aciklama="lol", ozet="sum", hashtagler=["pazar"])
    client.models.generate_content = lambda model, contents, config: NS(parsed=meta, text=meta.model_dump_json())

    s = script.write_scenario(client, channel, "a bazaar")
    profile, message, project = sent[0]
    assert profile == "P1" and project == "shitpost gen"
    assert message == "Daha önce yapmadığın komik bir prompt yaz."
    assert s.video_prompt.startswith("Spoderman slips") and s.ilk_kare == ""
    assert s.baslik == "Spoderman pazarda"
    prompt = script.web_video_prompt(channel, s)
    assert "the costume guy slips" in prompt and "spoderman" not in prompt.lower()


def test_chatgpt_prompt_sent_as_is_then_aliased_on_copyright(channel, tmp_path, web_env, monkeypatch):
    channel.scenario["motor"] = "chatgpt_web"
    raw = "Spoderman hands Orange a square tomato and says 'Bu ne?'"
    s = script.Scenario(baslik="t", aciklama="a", ozet="o", ilk_kare="", video_prompt=raw, hashtagler=[])
    monkeypatch.setattr(script, "write_scenario", lambda *a, **k: s)
    web_env.behavior.append("copyright")
    result = run(FakeClient(), channel, tmp_path, publish=False)
    prompts = [c[1] for c in web_env.calls]
    assert prompts[0] == raw
    assert prompts[1].startswith("The costume guy is a skinny goofy guy")
    assert prompts[1].endswith("the costume guy hands the talking orange a square tomato and says 'Bu ne?'")
    assert "spoderman" not in prompts[1].lower()
    assert [c[0] for c in web_env.calls] == ["P1", "P1"]
    assert (result.folder / "gemini_prompt_1.txt").read_text() == raw


def test_chatgpt_scenario_survives_gemini_api_outage(channel, monkeypatch):
    from google.genai import errors

    from shitpost import chatgpt_web

    channel.scenario["motor"] = "chatgpt_web"
    monkeypatch.setenv("CHATGPT_PROFILI", "P1")
    monkeypatch.setattr(script, "_sleep", lambda s: (_ for _ in ()).throw(AssertionError("should not wait")))
    monkeypatch.setattr(chatgpt_web, "ask", lambda *a, **k: "Spoderman and Orange argue about a very long pineapple.")
    client = FakeClient()

    def busy(model, contents, config):
        raise errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})

    client.models.generate_content = busy
    s = script.write_scenario(client, channel, "x", log=lambda *a: None)
    assert s.baslik == channel.name and s.video_prompt.startswith("Spoderman and Orange")


def test_web_engine_busy_tries_other_account_then_waits(channel, tmp_path, web_env, monkeypatch):
    waits = []
    monkeypatch.setattr(pipeline, "_sleep", waits.append)
    web_env.behavior.extend(["busy", "busy", "busy"])
    result = run(FakeClient(), channel, tmp_path, publish=False)
    assert [c[0] for c in web_env.calls] == ["P1", "P2", "P1", "P2"]
    assert waits == [pipeline.BUSY_WAIT_SECONDS]
    assert result.video.read_bytes() == b"webvideo"


def test_web_engine_gives_up_when_always_busy(channel, tmp_path, web_env, monkeypatch):
    monkeypatch.setattr(pipeline, "_sleep", lambda s: None)
    web_env.behavior.extend(["busy"] * 20)
    with pytest.raises(pipeline.GeminiBusyAll):
        run(FakeClient(), channel, tmp_path, publish=False)
    assert len(web_env.calls) == 2 * pipeline.BUSY_ROUNDS


def test_chatgpt_placeholder_and_thought_header():
    from shitpost import chatgpt_web

    assert not chatgpt_web._is_final("Düşünüyor")
    assert not chatgpt_web._is_final("Thinking…")
    assert chatgpt_web._is_final("Spoderman tries to pay for a single tomato with a 500 lira note at the bazaar.")
    assert chatgpt_web._is_final("Thought for 8s\nSpoderman tries to pay for a single tomato with a 500 lira note.")
    assert not chatgpt_web._is_final("Thought for 8s\nDüşünüyor")
    raw = "Thought for 12s\nSpoderman tries to pay for a single tomato with a 500 lira note."
    assert script.clean_chatgpt_output(raw).startswith("Spoderman tries")


def test_aliases_cover_other_names(channel):
    s = script.Scenario(baslik="t", aciklama="a", ozet="o", ilk_kare="",
                        video_prompt="Spoderman and Annoying Orange fight. Orange laughs at Spider-Man.", hashtagler=[])
    prompt = script.web_video_prompt(channel, s)
    low = prompt.lower()
    assert "spoderman" not in low and "annoying orange" not in low and "spider-man" not in low
    assert "the costume guy and the talking orange fight" in low


def test_generic_gemini_error_retries_with_aliases_first(channel, tmp_path, web_env, monkeypatch):
    channel.scenario["motor"] = "chatgpt_web"
    raw = "Spoderman meets Annoying Orange."
    s = script.Scenario(baslik="t", aciklama="a", ozet="o", ilk_kare="", video_prompt=raw, hashtagler=[])
    monkeypatch.setattr(script, "write_scenario", lambda *a, **k: s)
    monkeypatch.setattr(pipeline, "_sleep", lambda s: None)
    calls = []

    def fake(profile, prompt, out_path, log=print, **kw):
        calls.append((profile, prompt))
        if len(calls) == 1:
            raise video_web.GeminiBusy("Sorry, something went wrong. Please try your request again.")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"ok")
        return out_path

    monkeypatch.setattr(video_web, "generate_video_web", fake)
    run(FakeClient(), channel, tmp_path, publish=False)
    assert [c[0] for c in calls] == ["P1", "P1"]
    assert calls[0][1] == raw and "spoderman" not in calls[1][1].lower()


def test_with_deadline_gives_up_on_hung_call():
    import threading

    from shitpost import script

    hang = threading.Event()
    with pytest.raises(TimeoutError):
        script._with_deadline(lambda: hang.wait(5), 0.2)
    hang.set()
    assert script._with_deadline(lambda: 7, 1) == 7


def test_hard_time_reply_counts_as_refusal():
    from shitpost import video_web

    text = "i'm having a hard time fulfilling your request. can i help you with something else instead?"
    assert any(ph in text for ph in video_web.REFUSAL_PHRASES)
