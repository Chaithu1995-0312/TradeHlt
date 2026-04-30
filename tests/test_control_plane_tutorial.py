from __future__ import annotations

from src.control_plane.jobs import JobManager
from src.control_plane.server import ControlPlaneAPI


def test_tour_persistence_keys_present_in_ui_html() -> None:
    api = ControlPlaneAPI(JobManager())
    html = api.ui_html()
    assert "tutorial_seen" in html
    assert "tutorial_dismissed_version" in html
    assert "tutorial_progress" in html
    assert "playbook_completed" in html


def test_tour_controls_present_in_ui_html() -> None:
    api = ControlPlaneAPI(JobManager())
    html = api.ui_html()
    assert "startTour(true)" in html
    assert "skipTour" in html
    assert "tourNextBtn" in html
    assert "tourBackBtn" in html

