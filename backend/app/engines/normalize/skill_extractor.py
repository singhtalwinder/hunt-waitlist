"""Skill extraction from job titles and descriptions."""

import re
from typing import Set


class SkillExtractor:
    """Extracts and normalizes technical skills from job postings."""

    # Known skills with aliases
    SKILL_ALIASES = {
        # Programming Languages
        "python": ["python", "python3", "py"],
        "javascript": ["javascript", "js", "ecmascript", "es6", "es2015"],
        "typescript": ["typescript", "ts"],
        "java": ["java"],
        "golang": ["golang", "go lang", "go-lang"],
        "rust": ["rust", "rustlang"],
        "c++": ["c++", "cpp", "c plus plus"],
        "c#": ["c#", "csharp", "c-sharp", ".net"],
        "ruby": ["ruby"],
        "php": ["php"],
        "swift": ["swift"],
        "kotlin": ["kotlin"],
        "scala": ["scala"],
        "r": ["\\br\\b"],
        "sql": ["sql", "mysql", "postgresql", "postgres", "mssql", "sqlite"],

        # Frontend
        "react": ["react", "reactjs", "react.js"],
        "vue": ["vue", "vuejs", "vue.js"],
        "angular": ["angular", "angularjs"],
        "svelte": ["svelte", "sveltekit"],
        "nextjs": ["next.js", "nextjs", "next js"],
        "nuxt": ["nuxt", "nuxtjs"],
        "html": ["html", "html5"],
        "css": ["css", "css3", "scss", "sass", "less"],
        "tailwind": ["tailwind", "tailwindcss"],

        # Backend
        "nodejs": ["node.js", "nodejs", "node js"],
        "django": ["django"],
        "flask": ["flask"],
        "fastapi": ["fastapi", "fast api"],
        "express": ["express", "expressjs"],
        "rails": ["rails", "ruby on rails"],
        "spring": ["spring", "spring boot", "springboot"],
        "graphql": ["graphql", "graph ql"],
        "rest": ["rest", "restful", "rest api"],

        # Cloud & Infrastructure
        "aws": ["aws", "amazon web services"],
        "gcp": ["gcp", "google cloud", "google cloud platform"],
        "azure": ["azure", "microsoft azure"],
        "kubernetes": ["kubernetes", "k8s"],
        "docker": ["docker", "containers"],
        "terraform": ["terraform"],
        "ansible": ["ansible"],
        "jenkins": ["jenkins"],
        "circleci": ["circleci", "circle ci"],
        "github actions": ["github actions", "gh actions"],

        # Databases
        "postgresql": ["postgresql", "postgres", "psql"],
        "mysql": ["mysql"],
        "mongodb": ["mongodb", "mongo"],
        "redis": ["redis"],
        "elasticsearch": ["elasticsearch", "elastic"],
        "dynamodb": ["dynamodb", "dynamo"],
        "cassandra": ["cassandra"],
        "neo4j": ["neo4j"],

        # Data & ML
        "pandas": ["pandas"],
        "numpy": ["numpy"],
        "pytorch": ["pytorch", "torch"],
        "tensorflow": ["tensorflow", "tf"],
        "scikit-learn": ["scikit-learn", "sklearn"],
        "spark": ["spark", "apache spark", "pyspark"],
        "kafka": ["kafka", "apache kafka"],
        "airflow": ["airflow", "apache airflow"],
        "dbt": ["dbt"],

        # Tools & Practices
        "git": ["git", "github", "gitlab", "bitbucket"],
        "agile": ["agile", "scrum", "kanban"],
        "ci/cd": ["ci/cd", "cicd", "continuous integration", "continuous deployment"],
        "tdd": ["tdd", "test driven development"],
        "microservices": ["microservices", "micro-services"],
        "api design": ["api design", "api development"],
        "linux": ["linux", "unix"],
    }

    def __init__(self):
        # Build pattern map
        self.skill_patterns = {}
        for canonical, aliases in self.SKILL_ALIASES.items():
            patterns = []
            for alias in aliases:
                # Handle special regex patterns
                if alias.startswith("\\b"):
                    patterns.append(re.compile(alias, re.IGNORECASE))
                else:
                    # Escape special chars and add word boundaries
                    escaped = re.escape(alias)
                    patterns.append(re.compile(rf"\b{escaped}\b", re.IGNORECASE))
            self.skill_patterns[canonical] = patterns

    def extract(self, title: str, description: str = "") -> list[str]:
        """
        Extract skills from job title and description.

        Returns sorted list of canonical skill names.
        """
        text = f"{title} {description}"
        found_skills: Set[str] = set()

        for canonical, patterns in self.skill_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    found_skills.add(canonical)
                    break  # Found this skill, move to next

        return sorted(list(found_skills))

    def normalize_skill(self, skill: str) -> str:
        """Normalize a single skill name to canonical form."""
        skill_lower = skill.lower().strip()

        for canonical, aliases in self.SKILL_ALIASES.items():
            if skill_lower in [a.lower() for a in aliases]:
                return canonical

        return skill_lower

    def get_related_skills(self, skill: str) -> list[str]:
        """Get skills commonly associated with a given skill."""
        SKILL_RELATIONS = {
            "react": ["javascript", "typescript", "nextjs", "html", "css"],
            "vue": ["javascript", "typescript", "nuxt", "html", "css"],
            "angular": ["typescript", "html", "css"],
            "python": ["django", "flask", "fastapi", "pandas", "numpy"],
            "java": ["spring", "maven", "gradle"],
            "nodejs": ["javascript", "typescript", "express"],
            "kubernetes": ["docker", "aws", "gcp", "azure"],
            "aws": ["terraform", "docker", "kubernetes"],
            "postgresql": ["sql"],
            "mongodb": ["nodejs"],
            "pytorch": ["python", "numpy"],
            "tensorflow": ["python", "numpy"],
        }

        canonical = self.normalize_skill(skill)
        return SKILL_RELATIONS.get(canonical, [])
