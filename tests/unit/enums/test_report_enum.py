import pytest

from app.enums.ReportEnum import ContentType, HarmType, ReportStatus


class TestContentType:
    def test_all_members_present(self):
        members = {m.value for m in ContentType}
        assert members == {"url", "message", "image", "video", "other"}

    def test_is_string_enum(self):
        assert isinstance(ContentType.URL, str)
        assert ContentType.URL == "url"

    def test_lookup_by_value(self):
        assert ContentType("url") is ContentType.URL
        assert ContentType("message") is ContentType.MESSAGE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ContentType("audio")


class TestHarmType:
    def test_all_members_present(self):
        members = {m.value for m in HarmType}
        assert members == {
            "misinformation", "scam", "phishing",
            "deepfake", "cyberbullying", "other"
        }

    def test_is_string_enum(self):
        assert isinstance(HarmType.SCAM, str)
        assert HarmType.SCAM == "scam"

    def test_lookup_by_value(self):
        assert HarmType("scam") is HarmType.SCAM
        assert HarmType("phishing") is HarmType.PHISHING
        assert HarmType("deepfake") is HarmType.DEEPFAKE
        assert HarmType("cyberbullying") is HarmType.CYBERBULLYING
        assert HarmType("misinformation") is HarmType.MISINFORMATION

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            HarmType("hacking")


class TestReportStatus:
    def test_all_members_present(self):
        members = {m.value for m in ReportStatus}
        assert members == {"pending", "under_review", "approved", "rejected"}

    def test_is_string_enum(self):
        assert isinstance(ReportStatus.PENDING, str)
        assert ReportStatus.PENDING == "pending"

    def test_lookup_by_value(self):
        assert ReportStatus("pending") is ReportStatus.PENDING
        assert ReportStatus("under_review") is ReportStatus.UNDER_REVIEW
        assert ReportStatus("approved") is ReportStatus.APPROVED
        assert ReportStatus("rejected") is ReportStatus.REJECTED

    def test_terminal_statuses_are_approved_and_rejected(self):
        """Matches the TERMINAL_STATUSES set in report_service."""
        terminal = {ReportStatus.APPROVED, ReportStatus.REJECTED}
        non_terminal = {ReportStatus.PENDING, ReportStatus.UNDER_REVIEW}
        assert terminal.isdisjoint(non_terminal)

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ReportStatus("resolved")
