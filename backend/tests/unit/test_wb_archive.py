"""Synthetic counterexamples for archive integrity; never source qualification."""

import csv
import io
import stat
import zipfile

import pytest

from ketrika.core import wb_archive as wb

MEMBER = "MDG_RTFP_mkt_2007_2026-10-05.csv"
HEADERS = (*wb.GRAIN, "c_rice")
ROW = [
    "MDG",
    "Madagascar",
    "Market Average",
    "Market Average",
    "Market Average",
    "",
    "",
    "gid_mdg_national_average",
    "2026-09-01",
    "MGA",
    "1234.567890",
]


def packet(rows=None, headers=HEADERS, member=MEMBER, extra=False, mode=None):
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(headers)
    writer.writerows([ROW] if rows is None else rows)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        info = zipfile.ZipInfo(member)
        if mode is not None:
            info.external_attr = mode << 16
        archive.writestr(info, text.getvalue())
        if extra:
            archive.writestr("extra.csv", "x")
    return output.getvalue()


def test_original_lexeme_and_explicit_national_scope():
    result = wb.cells(packet(), [[MEMBER, 0, "c_rice"], [MEMBER, 0, "mkt_name"]])
    assert result[(MEMBER, 0, "c_rice")] == "1234.567890"
    assert result[(MEMBER, 0, "mkt_name")] == "Market Average"
    assert dict(wb.rows(packet(), MEMBER))[0]["lat"] == ""


@pytest.mark.parametrize(
    "name", ["../outside.csv", "/abs.csv", "data.csv", "MDG_RTFP_mkt_2007_2026-02-30.csv"]
)
def test_member_name_is_closed(name):
    with pytest.raises(wb.ArchiveError, match="member_invalid"):
        list(wb.rows(packet(member=name), name))


@pytest.mark.parametrize(
    "kwargs", [{"extra": True}, {"mode": stat.S_IFLNK | 0o777}, {"headers": (*HEADERS, "c_rice")}]
)
def test_extra_members_symlinks_and_duplicate_headers_refused(kwargs):
    with pytest.raises(wb.ArchiveError):
        list(wb.rows(packet(**kwargs), MEMBER))


@pytest.mark.parametrize("row", [ROW[:-1], ["FRA", *ROW[1:]], [*ROW[:8], "2026-09-02", *ROW[9:]]])
def test_invalid_rows_refused(row):
    with pytest.raises(wb.ArchiveError):
        list(wb.rows(packet(rows=[row]), MEMBER))


def test_unseen_tail_and_duplicate_grain_are_validated():
    with pytest.raises(wb.ArchiveError, match="duplicate_grain"):
        wb.cells(packet(rows=[ROW, ROW]), [[MEMBER, 0, "c_rice"]])
    with pytest.raises(wb.ArchiveError, match="row_invalid"):
        wb.cells(packet(rows=[ROW, ROW[:-1]]), [[MEMBER, 0, "c_rice"]])


def test_crc_failure_refused():
    content = packet()
    content = content.replace(b"1234.567890", b"9234.567890", 1)
    with pytest.raises(wb.ArchiveError, match="archive_invalid"):
        wb.cells(content, [[MEMBER, 0, "c_rice"]])


@pytest.mark.parametrize("constant", ["MAX_ARCHIVE_BYTES", "MAX_MEMBER_BYTES", "MAX_ROWS"])
def test_resource_bounds_refused(monkeypatch, constant):
    monkeypatch.setattr(wb, constant, 0)
    with pytest.raises(wb.ArchiveError):
        list(wb.rows(packet(), MEMBER))


@pytest.mark.parametrize(
    "coordinates",
    [
        [],
        [[MEMBER, True, "c_rice"]],
        [[MEMBER, -1, "c_rice"]],
        [[MEMBER, 1, "c_rice"]],
        [[MEMBER, 0, "absent"]],
        [[MEMBER, 0, "c_rice"], [MEMBER, 0, "c_rice"]],
    ],
)
def test_coordinates_are_exact_and_unambiguous(coordinates):
    with pytest.raises(wb.ArchiveError):
        wb.cells(packet(), coordinates)


def test_missing_value_is_preserved_as_missing():
    assert wb.cells(packet(rows=[[*ROW[:-1], ""]]), [[MEMBER, 0, "c_rice"]]) == {
        (MEMBER, 0, "c_rice"): ""
    }
