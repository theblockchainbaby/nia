from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT

NAME = "[Your Name]"
HEADLINE = "AI Solutions Architect &middot; Forward Deployed Engineer"
CONTACT = "[city, state] &nbsp;|&nbsp; [email] &nbsp;|&nbsp; [phone] &nbsp;|&nbsp; [linkedin / github]"

SUMMARY = (
    "Self-directed technologist with 10+ years building and running a technology-led "
    "business end-to-end. Strengths in deploying AI and automation into real "
    "operations, integrating data across systems, and turning ambiguous problems "
    "into shipped software. Comfortable embedding directly with customers to "
    "translate workflows into working tooling &mdash; the core pattern of a "
    "Palantir Forward Deployed role."
)

EXPERIENCE = [
    {
        "title": "Founder / CEO",
        "company": "Self-Employed",
        "dates": "Mar 2015 &ndash; Present",
        "bullets": [
            "Run a one-person technology and services business: own product direction, delivery, customer relationships, and back-office operations.",
            "Deploy AI and automation (LLM workflows, RPA, prompt engineering) to replace manual processes for clients and for internal operations.",
            "Build and maintain full-stack software and integrations across CRM (HubSpot), ticketing/PSA (ConnectWise), and data warehouses (Snowflake, Redshift).",
            "Stand up dashboards and reporting in Power BI and Excel against warehoused data to drive operating decisions.",
            "Administer IT infrastructure end-to-end: Windows servers, networking, firewall / IPS, VoIP, backup, and security hardening.",
            "Author SOPs, runbooks, and technical documentation so processes survive past the founder.",
        ],
    },
    {
        "title": "Manager",
        "company": "[Employer]",
        "dates": "From Feb 2012",
        "bullets": [
            "Led a cross-functional team; owned performance management, staff development, and conflict resolution.",
            "Drove process improvement and standard-operating-procedure rollouts across the team.",
            "Coordinated project teams and resource planning to hit delivery targets.",
        ],
    },
    {
        "title": "Point Guard",
        "company": "Professional Basketball",
        "dates": "From Sep 2009",
        "bullets": [
            "Competed at the professional level &mdash; point guard is, in practice, real-time decision-making, leadership, and orchestrating a team under pressure.",
            "Habits from this period (daily reps, film study, accountability) carry directly into engineering work.",
        ],
    },
    {
        "title": "Customer Service Clerk",
        "company": "Trader Joe's",
        "dates": "From Mar 2008",
        "bullets": [
            "Front-line customer service in a high-throughput retail environment.",
        ],
    },
]

EDUCATION = "[Degree, Institution, Year] &mdash; add or remove as applicable"

SKILLS = [
    ("AI &amp; Data",
     "Generative AI / LLMs, prompt engineering, AI implementation, Python, "
     "Snowflake, Redshift, Power BI, dashboard development, log analysis"),
    ("Software &amp; Infra",
     "Full-stack development, backend systems, APIs, build automation, "
     "debugging, software testing, server administration, IT infrastructure, "
     "computer networking, firewalls / IPS, system security, VoIP, Windows"),
    ("Delivery &amp; Ops",
     "Cross-functional collaboration, project management, ClickUp, HubSpot CRM, "
     "ConnectWise, SOPs &amp; technical documentation, process improvement, "
     "performance management, leadership, self-starter"),
]

# ---------- styles ----------
DARK = HexColor("#111111")
GREY = HexColor("#555555")
RULE = HexColor("#bdbdbd")

styles = {
    "name": ParagraphStyle(
        "name", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=DARK,
    ),
    "headline": ParagraphStyle(
        "headline", fontName="Helvetica", fontSize=11, leading=14, textColor=GREY,
    ),
    "contact": ParagraphStyle(
        "contact", fontName="Helvetica", fontSize=9.5, leading=13, textColor=GREY,
    ),
    "section": ParagraphStyle(
        "section", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
        textColor=DARK, spaceBefore=8, spaceAfter=2,
    ),
    "body": ParagraphStyle(
        "body", fontName="Helvetica", fontSize=10, leading=13, textColor=DARK,
    ),
    "jobtitle": ParagraphStyle(
        "jobtitle", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=DARK,
        spaceBefore=4,
    ),
    "jobmeta": ParagraphStyle(
        "jobmeta", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=GREY,
    ),
    "bullet": ParagraphStyle(
        "bullet", fontName="Helvetica", fontSize=9.7, leading=12.5, textColor=DARK,
    ),
    "skillrow": ParagraphStyle(
        "skillrow", fontName="Helvetica", fontSize=9.7, leading=12.5, textColor=DARK,
    ),
}


def section_block(label):
    return [
        Paragraph(label.upper(), styles["section"]),
        HRFlowable(width="100%", thickness=0.5, color=RULE, spaceBefore=0, spaceAfter=4),
    ]


def build():
    out = "/home/user/nia/Resume_Palantir.pdf"
    doc = SimpleDocTemplate(
        out, pagesize=LETTER,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
        title="Resume", author=NAME,
    )

    story = []
    story.append(Paragraph(NAME, styles["name"]))
    story.append(Paragraph(HEADLINE, styles["headline"]))
    story.append(Paragraph(CONTACT, styles["contact"]))
    story.append(Spacer(1, 6))

    story += section_block("Summary")
    story.append(Paragraph(SUMMARY, styles["body"]))

    story += section_block("Experience")
    for job in EXPERIENCE:
        story.append(Paragraph(f"{job['title']} &mdash; {job['company']}", styles["jobtitle"]))
        story.append(Paragraph(job["dates"], styles["jobmeta"]))
        bullets = [ListItem(Paragraph(b, styles["bullet"]), leftIndent=10, value="bullet")
                   for b in job["bullets"]]
        story.append(ListFlowable(bullets, bulletType="bullet", leftIndent=14, bulletFontSize=8))
        story.append(Spacer(1, 2))

    story += section_block("Skills")
    for label, text in SKILLS:
        story.append(Paragraph(f"<b>{label}:</b> {text}", styles["skillrow"]))
        story.append(Spacer(1, 1))

    story += section_block("Education")
    story.append(Paragraph(EDUCATION, styles["body"]))

    doc.build(story)
    print(out)


if __name__ == "__main__":
    build()
