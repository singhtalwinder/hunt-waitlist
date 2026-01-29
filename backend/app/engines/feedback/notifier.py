"""Email notification service using Resend."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import resend
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db import CandidateProfile, Match, Job, Company
from app.engines.feedback.explainer import FeedbackEngine

settings = get_settings()
logger = structlog.get_logger()

# Initialize Resend
resend.api_key = settings.resend_api_key


class EmailNotifier:
    """Email notification service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.feedback_engine = FeedbackEngine(db)

    async def send_weekly_digest(
        self,
        candidate_id: UUID,
    ) -> bool:
        """Send weekly job digest email to a candidate."""
        # Get candidate
        result = await self.db.execute(
            select(CandidateProfile).where(CandidateProfile.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()

        if not candidate or not candidate.email:
            logger.warning("Candidate not found or no email", candidate_id=str(candidate_id))
            return False

        # Get recent matches
        week_ago = datetime.utcnow() - timedelta(days=7)
        result = await self.db.execute(
            select(Match)
            .options(selectinload(Match.job).selectinload(Job.company))
            .where(
                Match.candidate_id == candidate_id,
                Match.score >= settings.match_score_threshold,
                Match.created_at >= week_ago,
            )
            .order_by(Match.score.desc())
            .limit(10)
        )
        matches = result.scalars().all()

        if not matches:
            # Send "no matches" email
            return await self._send_no_matches_email(candidate)

        # Build email content
        subject = f"🎯 {len(matches)} new jobs matched for you this week"
        html_content = await self._build_digest_html(candidate, matches)

        return await self._send_email(
            to=candidate.email,
            subject=subject,
            html=html_content,
        )

    async def _send_no_matches_email(
        self,
        candidate: CandidateProfile,
    ) -> bool:
        """Send email when no matches found."""
        explanation = await self.feedback_engine.explain_no_matches(candidate.id)

        subject = "No new matches this week - but we're still looking!"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1a1a1a; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 24px; font-weight: bold; }}
                .logo span {{ color: #FF4500; }}
                .message {{ background: #f9f9f9; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .suggestions {{ margin-top: 20px; }}
                .suggestions li {{ margin-bottom: 10px; }}
                .footer {{ text-align: center; font-size: 12px; color: #666; margin-top: 40px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">hunt<span>.</span></div>
                </div>
                
                <p>Hi {candidate.name or 'there'},</p>
                
                <div class="message">
                    <p><strong>{explanation.reason}</strong></p>
                    
                    <div class="suggestions">
                        <p>Here are some suggestions:</p>
                        <ul>
                            {''.join(f'<li>{s}</li>' for s in explanation.suggestions)}
                        </ul>
                    </div>
                </div>
                
                <p>We check for new jobs multiple times a day and will email you as soon as we find matches.</p>
                
                <div class="footer">
                    <p>© 2025 Hunt. You're receiving this because you signed up for job alerts.</p>
                    <p><a href="#">Unsubscribe</a> | <a href="#">Update preferences</a></p>
                </div>
            </div>
        </body>
        </html>
        """

        return await self._send_email(
            to=candidate.email,
            subject=subject,
            html=html_content,
        )

    async def _build_digest_html(
        self,
        candidate: CandidateProfile,
        matches: list[Match],
    ) -> str:
        """Build HTML content for digest email."""
        job_cards = ""

        for match in matches:
            job = match.job
            company = job.company
            explanation = await self.feedback_engine.explain_match(match.id)

            factors_html = ""
            if explanation:
                factors_html = "".join(f"<li>{f}</li>" for f in explanation.factors[:3])

            score_badge = ""
            if match.score >= 0.8:
                score_badge = '<span style="background: #22c55e; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">Strong match</span>'
            elif match.score >= 0.6:
                score_badge = '<span style="background: #3b82f6; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">Good match</span>'

            location_text = ""
            if job.location_type == "remote":
                location_text = "Remote"
            elif job.locations:
                location_text = job.locations[0]

            job_cards += f"""
            <div style="border: 1px solid #e5e5e5; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                    <div>
                        <h3 style="margin: 0 0 4px 0; font-size: 16px;">{job.title}</h3>
                        <p style="margin: 0; color: #666; font-size: 14px;">{company.name} • {location_text}</p>
                    </div>
                    {score_badge}
                </div>
                
                <ul style="margin: 12px 0; padding-left: 20px; font-size: 14px; color: #444;">
                    {factors_html}
                </ul>
                
                <a href="{job.source_url}" style="display: inline-block; background: #FF4500; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 500;">
                    View Job →
                </a>
            </div>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1a1a1a; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ text-align: center; margin-bottom: 30px; }}
                .logo {{ font-size: 24px; font-weight: bold; }}
                .logo span {{ color: #FF4500; }}
                .summary {{ background: #f9f9f9; padding: 16px; border-radius: 8px; margin-bottom: 24px; text-align: center; }}
                .jobs {{ margin-bottom: 24px; }}
                .footer {{ text-align: center; font-size: 12px; color: #666; margin-top: 40px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">hunt<span>.</span></div>
                </div>
                
                <p>Hi {candidate.name or 'there'},</p>
                
                <div class="summary">
                    <p style="margin: 0; font-size: 18px; font-weight: 500;">
                        We found <strong>{len(matches)} jobs</strong> that match your profile this week!
                    </p>
                </div>
                
                <div class="jobs">
                    {job_cards}
                </div>
                
                <p style="text-align: center;">
                    <a href="#" style="color: #FF4500; text-decoration: none; font-weight: 500;">
                        View all matches in your dashboard →
                    </a>
                </p>
                
                <div class="footer">
                    <p>© 2025 Hunt. You're receiving this because you signed up for job alerts.</p>
                    <p><a href="#">Unsubscribe</a> | <a href="#">Update preferences</a></p>
                </div>
            </div>
        </body>
        </html>
        """

        return html_content

    async def _send_email(
        self,
        to: str,
        subject: str,
        html: str,
    ) -> bool:
        """Send email via Resend."""
        if not settings.resend_api_key:
            logger.warning("Resend API key not configured, skipping email")
            return False

        try:
            resend.Emails.send({
                "from": settings.email_from,
                "to": to,
                "subject": subject,
                "html": html,
            })

            logger.info("Email sent", to=to, subject=subject)
            return True

        except Exception as e:
            logger.error("Failed to send email", to=to, error=str(e))
            return False


async def send_digest(candidate_id: str):
    """Send digest to a single candidate (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        notifier = EmailNotifier(db)
        success = await notifier.send_weekly_digest(UUID(candidate_id))

        if success:
            # Update last notified timestamp
            result = await db.execute(
                select(CandidateProfile).where(CandidateProfile.id == UUID(candidate_id))
            )
            candidate = result.scalar_one_or_none()
            if candidate:
                candidate.last_notified_at = datetime.utcnow()
                await db.commit()


async def send_all_digests():
    """Send digests to all eligible candidates (for background task)."""
    from app.db import async_session_factory

    async with async_session_factory() as db:
        # Get candidates who haven't been notified in the last 6 days
        cutoff = datetime.utcnow() - timedelta(days=6)

        result = await db.execute(
            select(CandidateProfile).where(
                CandidateProfile.is_active == True,
                (CandidateProfile.last_notified_at < cutoff) | (CandidateProfile.last_notified_at.is_(None)),
            )
        )
        candidates = result.scalars().all()

        notifier = EmailNotifier(db)
        sent = 0
        failed = 0

        for candidate in candidates:
            try:
                success = await notifier.send_weekly_digest(candidate.id)
                if success:
                    candidate.last_notified_at = datetime.utcnow()
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(
                    "Digest failed",
                    candidate_id=str(candidate.id),
                    error=str(e),
                )
                failed += 1

        await db.commit()

        logger.info(
            "Digest send complete",
            total=len(candidates),
            sent=sent,
            failed=failed,
        )
