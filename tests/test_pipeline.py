import json
import random
import shutil
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from google.genai import types

from shitpost import history, pipeline, script
from shitpost.config import CHANNELS_DIR, load_channel
from shitpost.publish import Post

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


def run(client, channel, tmp_path, **kw):
    return pipeline.run(client, channel, out_root=tmp_path / "cikti", log=lambda *a: None,
                        sleep=lambda s: None, rng=random.Random(1), **kw)


def test_channel_config_loads(channel):
    assert [c.name for c in channel.characters] == ["Spoderman", "Orange"]
    assert channel.video["en_boy"] == "9:16"
    assert set(channel.platforms) == {"youtube", "ayrshare"}


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


def test_dry_run_creates_outputs_without_history(channel, tmp_path):
    client = FakeClient()
    result = run(client, channel, tmp_path, publish=False)

    assert result.video.read_bytes() == b"mp4data"
    assert (result.folder / "ilk_kare.png").read_bytes() == PNG
    assert json.loads((result.folder / "senaryo.json").read_text())["baslik"] == "Title 1"
    assert all(c.reference.exists() for c in channel.characters)
    cfg = client.video_calls[0]["config"]
    assert cfg.aspect_ratio == "9:16" and cfg.duration_seconds == 8
    assert client.video_calls[0]["image"].image_bytes == PNG
    assert not channel.history_path.exists()


def test_filtered_video_retries_with_new_scenario(channel, tmp_path):
    client = FakeClient(filtered_times=1)
    result = run(client, channel, tmp_path, publish=False)
    assert len(client.video_calls) == 2
    assert result.scenario.baslik == "Title 2"


def test_gives_up_after_attempts(channel, tmp_path):
    with pytest.raises(RuntimeError, match="video üretilemedi"):
        run(FakeClient(filtered_times=5), channel, tmp_path, publish=False, attempts=2)


def test_publish_records_history(channel, tmp_path, monkeypatch):
    posts = []

    def fake_publish_all(ch, video, post):
        posts.append(post)
        return {"youtube": "https://youtube.com/shorts/x"}, {"ayrshare": "boom"}

    monkeypatch.setattr(pipeline, "publish_all", fake_publish_all)
    result = run(FakeClient(), channel, tmp_path)

    assert result.errors == {"ayrshare": "boom"}
    assert posts[0].hashtags == channel.hashtags + ["funny"]
    entry = history.load(channel.history_path)[-1]
    assert entry["ozet"] == "summary 1" and entry["linkler"]["youtube"].endswith("/x")


def test_caption_with_tags():
    post = Post(title="t", caption="lol", hashtags=["shorts", "#meme"])
    assert post.caption_with_tags() == "lol\n\n#shorts #meme"
