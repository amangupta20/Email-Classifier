"""populate_taxonomy_seed_data

Revision ID: aeec6eb7459b
Revises: a0c0f47850f1
Create Date: 2025-10-05 11:58:33.089742

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aeec6eb7459b'
down_revision: Union[str, Sequence[str], None] = 'a0c0f47850f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Insert comprehensive taxonomy from constitution v2
    op.execute("""
        INSERT INTO tags (name, description, category_type, active, priority_order, created_at) VALUES
        -- Academic (6 subtags)
        ('academic.coursework', 'Assignments, homework, project updates', 'ACADEMIC', true, 1, NOW()),
        ('academic.exams', 'Exam schedules, room assignments, practice tests', 'ACADEMIC', true, 2, NOW()),
        ('academic.lectures', 'Class schedules, lecture notes, recordings', 'ACADEMIC', true, 3, NOW()),
        ('academic.assignments', 'Homework assignments, project submissions, deadlines', 'ACADEMIC', true, 4, NOW()),
        ('academic.grades', 'Grade reports, transcripts, academic performance', 'ACADEMIC', true, 5, NOW()),
        ('academic.registration', 'Course registration, add/drop, academic advising', 'ACADEMIC', true, 6, NOW()),
        
        -- Career (5 subtags)
        ('career.internship', 'Internship offers, application deadlines, interview invitations', 'CAREER', true, 1, NOW()),
        ('career.job_search', 'Job applications, networking events, career fairs', 'CAREER', true, 2, NOW()),
        ('career.interviews', 'Interview scheduling, preparation, follow-ups', 'CAREER', true, 3, NOW()),
        ('career.networking', 'Professional connections, LinkedIn messages, referrals', 'CAREER', true, 4, NOW()),
        ('career.resume', 'Resume updates, portfolio reviews, career coaching', 'CAREER', true, 5, NOW()),
        
        -- Administrative (5 subtags)
        ('admin.billing', 'Tuition fees, payment plans, financial aid disbursements', 'ADMIN', true, 1, NOW()),
        ('admin.records', 'Transcripts, enrollment verification, document requests', 'ADMIN', true, 2, NOW()),
        ('admin.housing', 'Dorm applications, housing contracts, maintenance requests', 'ADMIN', true, 3, NOW()),
        ('admin.it_support', 'Tech support, account access, software licenses', 'ADMIN', true, 4, NOW()),
        ('admin.policies', 'Academic policies, code of conduct, regulations', 'ADMIN', true, 5, NOW()),
        
        -- Extracurricular (5 subtags) - Clubs, Sports, Cultural
        ('clubs.student_orgs', 'Club meetings, events, membership applications', 'CLUBS', true, 1, NOW()),
        ('sports.activities', 'Team practices, game schedules, athletic events', 'SPORTS', true, 1, NOW()),
        ('cultural.events', 'Cultural festivals, diversity events, celebrations', 'CULTURAL', true, 1, NOW()),
        ('extracurricular.volunteer', 'Volunteer opportunities, service hours, community service', 'CLUBS', true, 2, NOW()),
        ('extracurricular.leadership', 'Leadership roles, student government, committees', 'CLUBS', true, 3, NOW()),
        
        -- Time-Sensitive (5 subtags) - Action
        ('action.deadline_critical', '<24h, requires immediate attention', 'ACTION', true, 1, NOW()),
        ('action.deadline_urgent', '24-72h, high priority', 'ACTION', true, 2, NOW()),
        ('action.meeting_required', 'Meeting invitation, RSVP needed', 'ACTION', true, 3, NOW()),
        ('action.response_needed', 'Awaiting your reply or action', 'ACTION', true, 4, NOW()),
        ('action.follow_up', 'Requires follow-up action or check-in', 'ACTION', true, 5, NOW()),
        
        -- Financial (4 subtags)
        ('finance.scholarships', 'Scholarship applications, awards, renewal deadlines', 'FINANCE', true, 1, NOW()),
        ('finance.expenses', 'Personal expenses, budget alerts, spending reports', 'FINANCE', true, 2, NOW()),
        ('finance.aid', 'Financial aid applications, award letters, requirements', 'FINANCE', true, 3, NOW()),
        ('finance.refunds', 'Refund processing, stipends, reimbursements', 'FINANCE', true, 4, NOW()),
        
        -- Personal (3 subtags)
        ('personal.family', 'Family communications, personal relationships', 'PERSONAL', true, 1, NOW()),
        ('personal.health', 'Health appointments, wellness, medical information', 'PERSONAL', true, 2, NOW()),
        ('personal.social', 'Social events, personal invitations, leisure', 'PERSONAL', true, 3, NOW()),
        
        -- Learning (4 subtags)
        ('learning.online_courses', 'MOOCs, online tutorials, skill development', 'LEARNING', true, 1, NOW()),
        ('learning.workshops', 'Workshop registrations, training sessions', 'LEARNING', true, 2, NOW()),
        ('learning.research', 'Research opportunities, academic papers, publications', 'LEARNING', true, 3, NOW()),
        ('learning.certifications', 'Certification programs, professional development', 'LEARNING', true, 4, NOW()),
        
        -- Promotions (3 subtags)
        ('promotion.marketing', 'Marketing emails, advertisements, promotional content', 'PROMOTION', true, 1, NOW()),
        ('promotion.sales', 'Sales offers, discounts, commercial promotions', 'PROMOTION', true, 2, NOW()),
        ('promotion.events', 'Event promotions, webinars, conferences', 'PROMOTION', true, 3, NOW()),
        
        -- System (3 subtags)
        ('system.notifications', 'System alerts, maintenance notices, updates', 'SYSTEM', true, 1, NOW()),
        ('system.security', 'Security alerts, password resets, authentication', 'SYSTEM', true, 2, NOW()),
        ('system.backup', 'Backup notifications, data migration, system health', 'SYSTEM', true, 3, NOW()),
        
        -- Spam (3 subtags)
        ('spam.phishing', 'Phishing attempts, suspicious links, fraud', 'SPAM', true, 1, NOW()),
        ('spam.unsolicited', 'Unsolicited bulk emails, spam marketing', 'SPAM', true, 2, NOW()),
        ('spam.scam', 'Scam attempts, fraudulent schemes', 'SPAM', true, 3, NOW())
    ON CONFLICT (name) DO NOTHING;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove all seeded taxonomy data
    op.execute("""
        DELETE FROM tags WHERE name IN (
            'academic.coursework', 'academic.exams', 'academic.lectures', 'academic.assignments', 
            'academic.grades', 'academic.registration',
            'career.internship', 'career.job_search', 'career.interviews', 'career.networking', 'career.resume',
            'admin.billing', 'admin.records', 'admin.housing', 'admin.it_support', 'admin.policies',
            'clubs.student_orgs', 'sports.activities', 'cultural.events', 'extracurricular.volunteer', 'extracurricular.leadership',
            'action.deadline_critical', 'action.deadline_urgent', 'action.meeting_required', 'action.response_needed', 'action.follow_up',
            'finance.scholarships', 'finance.expenses', 'finance.aid', 'finance.refunds',
            'personal.family', 'personal.health', 'personal.social',
            'learning.online_courses', 'learning.workshops', 'learning.research', 'learning.certifications',
            'promotion.marketing', 'promotion.sales', 'promotion.events',
            'system.notifications', 'system.security', 'system.backup',
            'spam.phishing', 'spam.unsolicited', 'spam.scam'
        );
    """)
