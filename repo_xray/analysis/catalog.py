"""What each dependency, import or container image tells us about a project.

Kept as plain data so a new technology is one line, not new logic.
"""

from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass(frozen=True)
class Tech:
    name: str
    # "framework", "language", "database", "auth", "storage", "cache", "messaging",
    # "search", "platform", "external" or "tool".
    category: str
    # For frameworks: what kind of app they make ("api", "web", "mobile" or "desktop").
    role: str | None = None


def _framework(name: str, role: str) -> Tech:
    return Tech(name, "framework", role)


POSTGRES = Tech("PostgreSQL", "database")
MYSQL = Tech("MySQL", "database")
MONGODB = Tech("MongoDB", "database")
REDIS = Tech("Redis", "cache")
FIREBASE = Tech("Firebase", "platform")
FIREBASE_AUTH = Tech("Firebase Auth", "auth")
FIREBASE_STORAGE = Tech("Firebase Storage", "storage")
FIRESTORE = Tech("Firestore", "database")

# Maven artifactIds, npm packages and PyPI projects. Patterns use shell wildcards.
DEPENDENCIES: list[tuple[str, Tech]] = [
    # Java
    ("spring-boot-starter-web", _framework("Spring Boot", "api")),
    ("spring-boot-starter-webmvc", _framework("Spring Boot", "api")),
    ("spring-boot-starter-webflux", _framework("Spring Boot", "api")),
    ("quarkus-rest*", _framework("Quarkus", "api")),
    ("micronaut-http-server*", _framework("Micronaut", "api")),
    ("spring-boot-starter-data-jpa", Tech("JPA", "tool")),
    ("spring-boot-starter-security", Tech("Spring Security", "tool")),
    ("*flyway*", Tech("Flyway", "tool")),
    ("liquibase-core", Tech("Liquibase", "tool")),
    ("springdoc-openapi*", Tech("OpenAPI", "tool")),
    ("postgresql", POSTGRES),
    ("mysql-connector*", MYSQL),
    ("mariadb-java-client", Tech("MariaDB", "database")),
    ("spring-boot-starter-data-mongodb", MONGODB),
    ("spring-boot-starter-data-redis", REDIS),
    ("spring-kafka", Tech("Kafka", "messaging")),
    ("kafka-clients", Tech("Kafka", "messaging")),
    ("spring-boot-starter-amqp", Tech("RabbitMQ", "messaging")),
    ("firebase-admin", FIREBASE),
    ("stripe-java", Tech("Stripe", "external")),
    # JavaScript and TypeScript
    ("@angular/core", _framework("Angular", "web")),
    ("react", _framework("React", "web")),
    ("next", _framework("Next.js", "web")),
    ("vue", _framework("Vue", "web")),
    ("nuxt", _framework("Nuxt", "web")),
    ("svelte", _framework("Svelte", "web")),
    ("@sveltejs/kit", _framework("SvelteKit", "web")),
    ("express", _framework("Express", "api")),
    ("@nestjs/core", _framework("NestJS", "api")),
    ("fastify", _framework("Fastify", "api")),
    ("@capacitor/core", _framework("Capacitor", "mobile")),
    ("react-native", _framework("React Native", "mobile")),
    ("expo", _framework("Expo", "mobile")),
    ("electron", _framework("Electron", "desktop")),
    ("typescript", Tech("TypeScript", "language")),
    ("firebase", FIREBASE),
    ("@angular/fire", FIREBASE),
    ("@supabase/supabase-js", Tech("Supabase", "platform")),
    ("leaflet", Tech("Leaflet", "tool")),
    ("mapbox-gl", Tech("Mapbox", "external")),
    ("@prisma/client", Tech("Prisma", "tool")),
    ("mongoose", MONGODB),
    ("pg", POSTGRES),
    ("mysql2", MYSQL),
    ("ioredis", REDIS),
    ("stripe", Tech("Stripe", "external")),
    ("tailwindcss", Tech("Tailwind CSS", "tool")),
    # Python
    ("django", _framework("Django", "api")),
    ("flask", _framework("Flask", "api")),
    ("fastapi", _framework("FastAPI", "api")),
    ("streamlit", _framework("Streamlit", "web")),
    ("pyside6*", _framework("Qt for Python", "desktop")),
    ("pyqt*", _framework("PyQt", "desktop")),
    ("sqlalchemy", Tech("SQLAlchemy", "tool")),
    ("psycopg*", POSTGRES),
    ("pymongo", MONGODB),
    ("redis", REDIS),
    ("celery", Tech("Celery", "messaging")),
    ("openai", Tech("OpenAI API", "external")),
    ("anthropic", Tech("Claude API", "external")),
    ("ollama", Tech("Ollama", "external")),
]

# Prefixes of imported modules (Java packages, npm paths, Python modules).
IMPORTS: list[tuple[str, Tech]] = [
    ("com.google.firebase.auth", FIREBASE_AUTH),
    ("com.google.firebase.cloud", FIREBASE_STORAGE),
    ("com.google.cloud.storage", Tech("Cloud Storage", "storage")),
    ("com.google.cloud.firestore", FIRESTORE),
    ("firebase/auth", FIREBASE_AUTH),
    ("firebase/storage", FIREBASE_STORAGE),
    ("firebase/firestore", FIRESTORE),
    ("@angular/fire/auth", FIREBASE_AUTH),
    ("@angular/fire/storage", FIREBASE_STORAGE),
    ("@angular/fire/firestore", FIRESTORE),
    ("firebase_admin.auth", FIREBASE_AUTH),
    ("software.amazon.awssdk.services.s3", Tech("Amazon S3", "storage")),
    ("com.amazonaws.services.s3", Tech("Amazon S3", "storage")),
    ("boto3", Tech("AWS", "platform")),
    ("org.locationtech.jts", Tech("PostGIS", "database")),
]

# Docker images in compose files, matched by repository name.
IMAGES: list[tuple[str, Tech]] = [
    ("postgis/postgis", Tech("PostGIS", "database")),
    ("postgres", POSTGRES),
    ("mysql", MYSQL),
    ("mariadb", Tech("MariaDB", "database")),
    ("mongo", MONGODB),
    ("redis", REDIS),
    ("rabbitmq", Tech("RabbitMQ", "messaging")),
    ("*kafka*", Tech("Kafka", "messaging")),
    ("*elasticsearch*", Tech("Elasticsearch", "search")),
    ("minio/minio", Tech("MinIO", "storage")),
    ("*keycloak*", Tech("Keycloak", "auth")),
]

# Connection strings in configuration files.
CONNECTION_STRINGS: list[tuple[str, Tech]] = [
    ("jdbc:postgresql:", POSTGRES),
    ("jdbc:mysql:", MYSQL),
    ("mongodb://", MONGODB),
    ("mongodb+srv://", MONGODB),
    ("redis://", REDIS),
]

# A specific service makes a generic one redundant: "Firebase Auth" says more than "Firebase".
SUPERSEDES: dict[str, set[str]] = {
    "Firebase Auth": {"Firebase"},
    "Firebase Storage": {"Firebase", "Cloud Storage"},
    "Firestore": {"Firebase"},
}


def match_dependency(name: str) -> Tech | None:
    lowered = name.lower()
    return next((tech for pattern, tech in DEPENDENCIES if fnmatch(lowered, pattern)), None)


def match_import(module: str) -> Tech | None:
    return next((tech for prefix, tech in IMPORTS if module == prefix or module.startswith(prefix + ".")
                 or module.startswith(prefix + "/")), None)


def match_image(image: str) -> Tech | None:
    repository = image.split(":")[0].lower()
    return next((tech for pattern, tech in IMAGES if fnmatch(repository, pattern)), None)
