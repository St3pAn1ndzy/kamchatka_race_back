"""Read-only сервис для экрана «Контент»."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.faq_item import FAQItem
from app.db.models.news_post import NewsPost
from app.db.models.schedule_event import ScheduleEvent
from app.db.models.viewer_location import ViewerLocation


@dataclass
class ContentOverview:
    news_count: int
    schedule_count: int
    faq_count: int
    locations_count: int
    recent_news: list
    upcoming_events: list


class AdminContentService:
    """Сводка по контенту."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_overview(self) -> ContentOverview:
        news_count = (await self.session.execute(select(func.count(NewsPost.id)))).scalar() or 0
        schedule_count = (
            await self.session.execute(select(func.count(ScheduleEvent.id)))
        ).scalar() or 0
        faq_count = (await self.session.execute(select(func.count(FAQItem.id)))).scalar() or 0
        locations_count = (
            await self.session.execute(select(func.count(ViewerLocation.id)))
        ).scalar() or 0

        recent_news_stmt = select(NewsPost).order_by(NewsPost.created_at.desc()).limit(5)
        recent_rows = (await self.session.execute(recent_news_stmt)).scalars().all()
        recent_news = [
            {
                "id": n.id,
                "title": n.title,
                "is_published": n.is_published,
                "created_at": n.created_at.isoformat() if n.created_at else "",
            }
            for n in recent_rows
        ]

        upcoming_stmt = select(ScheduleEvent).order_by(ScheduleEvent.starts_at).limit(5)
        upcoming_rows = (await self.session.execute(upcoming_stmt)).scalars().all()
        upcoming_events = [
            {
                "id": e.id,
                "title": e.title,
                "starts_at": e.starts_at.isoformat() if e.starts_at else "",
                "kind": e.kind,
            }
            for e in upcoming_rows
        ]

        return ContentOverview(
            news_count=news_count,
            schedule_count=schedule_count,
            faq_count=faq_count,
            locations_count=locations_count,
            recent_news=recent_news,
            upcoming_events=upcoming_events,
        )
