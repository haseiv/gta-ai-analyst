from app.database.repository import AnalysisRepository


def test_analysis_survives_session(isolated_db):
    repo = AnalysisRepository()
    repo.create("A184", discord_user_id=7, guild_id=9, filename="clip.mp4")
    loaded = repo.get("A184")
    assert loaded is not None
    assert loaded.discord_user_id == 7
    repo.update("A184", status="COMPLETED", progress=100)
    assert repo.get("A184").status == "COMPLETED"
