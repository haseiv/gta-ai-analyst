import asyncio

from app.config.settings import Settings
from app.services.jobs import AnalysisJob, JobQueue


async def test_job_queue_processes_one_job(isolated_db):
    seen: list[str] = []

    async def handler(job: AnalysisJob) -> None:
        seen.append(job.analysis_id)
        job.status = "COMPLETED"
        job.progress = 100

    queue = JobQueue(Settings(max_concurrent_analyses=1, database_url="sqlite://"), handler)
    await queue.start()
    job = AnalysisJob(
        analysis_id="A1111",
        discord_user_id=1,
        video_url="https://example.invalid/video.mp4",
        filename="video.mp4",
        channel_id=1,
        interaction_token="token",
        application_id=1,
    )
    await queue.enqueue(job)
    await asyncio.wait_for(queue.queue.join(), timeout=2)
    await queue.stop()
    assert seen == ["A1111"]
    assert queue.get("A1111").status == "COMPLETED"
