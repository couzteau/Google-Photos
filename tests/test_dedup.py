"""Tests for degoogle_photos.dedup."""

from datetime import datetime
from pathlib import Path

from degoogle_photos.dedup import compute_md5, make_dedup_key, group_duplicates


def test_compute_md5(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"hello world")
    md5 = compute_md5(f)
    assert md5 == "5eb63bbbe01eeed093cb22bb8f5acdc3"


def test_compute_md5_different_content(tmp_path):
    f1 = tmp_path / "a.bin"
    f2 = tmp_path / "b.bin"
    f1.write_bytes(b"aaa")
    f2.write_bytes(b"bbb")
    assert compute_md5(f1) != compute_md5(f2)


def test_make_dedup_key_with_date():
    dt = datetime(2020, 5, 10, 14, 30, 45)
    key = make_dedup_key("abc123", dt)
    # Seconds should be rounded to 0
    assert key == ("abc123", "2020-05-10T14:30:00")


def test_make_dedup_key_without_date():
    key = make_dedup_key("abc123", None)
    assert key == ("abc123", None)


def test_make_dedup_key_same_minute_different_seconds():
    dt1 = datetime(2020, 5, 10, 14, 30, 10)
    dt2 = datetime(2020, 5, 10, 14, 30, 55)
    assert make_dedup_key("abc", dt1) == make_dedup_key("abc", dt2)


# ---------------------------------------------------------------------------
# group_duplicates
# ---------------------------------------------------------------------------

def test_group_duplicates_no_dupes(tmp_path):
    f1 = tmp_path / "a.jpg"
    f2 = tmp_path / "b.jpg"
    f1.write_bytes(b"aaa")
    f2.write_bytes(b"bbb")
    groups = group_duplicates([f1, f2])
    assert groups == []


def test_group_duplicates_finds_pair(tmp_path):
    content = b"identical"
    f1 = tmp_path / "original.jpg"
    f2 = tmp_path / "copy.jpg"
    f1.write_bytes(content)
    f2.write_bytes(content)
    groups = group_duplicates([f1, f2])
    assert len(groups) == 1
    md5, members = groups[0]
    assert len(members) == 2
    assert set(members) == {f1, f2}


def test_group_duplicates_three_copies(tmp_path):
    content = b"triplicate"
    files = [tmp_path / f"copy{i}.jpg" for i in range(3)]
    for f in files:
        f.write_bytes(content)
    groups = group_duplicates(files)
    assert len(groups) == 1
    _, members = groups[0]
    assert len(members) == 3


def test_group_duplicates_multiple_groups(tmp_path):
    (tmp_path / "a1.jpg").write_bytes(b"AAA")
    (tmp_path / "a2.jpg").write_bytes(b"AAA")
    (tmp_path / "b1.jpg").write_bytes(b"BBB")
    (tmp_path / "b2.jpg").write_bytes(b"BBB")
    (tmp_path / "unique.jpg").write_bytes(b"CCC")
    groups = group_duplicates(list(tmp_path.iterdir()))
    assert len(groups) == 2


def test_group_duplicates_keeper_is_shortest_path(tmp_path):
    """The file with the shortest absolute path string should be first (the keeper)."""
    deep = tmp_path / "sub" / "sub2" / "copy.jpg"
    shallow = tmp_path / "orig.jpg"
    deep.parent.mkdir(parents=True)
    content = b"same"
    deep.write_bytes(content)
    shallow.write_bytes(content)
    groups = group_duplicates([deep, shallow])
    assert len(groups) == 1
    _, members = groups[0]
    assert members[0] == shallow  # shorter path is keeper


def test_group_duplicates_progress_callback(tmp_path):
    files = []
    for i in range(5):
        f = tmp_path / f"file{i}.jpg"
        f.write_bytes(f"content{i}".encode())
        files.append(f)

    calls = []
    group_duplicates(files, progress_cb=lambda cur, tot: calls.append((cur, tot)))

    assert len(calls) == 5
    assert calls[-1] == (5, 5)
