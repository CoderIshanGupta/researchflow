from functools import lru_cache
import httpx
from app.core.config import settings


class SupabaseClient:
    """
    Minimal Supabase REST client using the service role key.
    Used for:
      - Auth signup/signin (backend-side)
      - Inserting/upserting/selecting from tables (papers, session_papers, etc.)
    """

    def __init__(self):
        self.url = settings.SUPABASE_URL.rstrip("/")
        self.key = settings.SUPABASE_KEY
        # 30s total timeout, 10s connect timeout
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def _get_headers(self, auth_token: str | None = None) -> dict:
        """
        Build headers for Supabase REST.
        We always use the service key on the backend for full access.
        """
        headers = {
            "apikey": self.key,
            "Content-Type": "application/json",
        }
        headers["Authorization"] = f"Bearer {self.key}"
        return headers

    # ---------- AUTH METHODS (used by /auth endpoints) ----------

    def auth_signup(self, email: str, password: str, metadata: dict | None = None) -> dict:
        """
        Create a Supabase auth user via REST.
        Used in /auth/signup.
        """
        url = f"{self.url}/auth/v1/signup"
        payload: dict = {
            "email": email,
            "password": password,
        }
        if metadata:
            payload["data"] = metadata

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=self._get_headers())
            if resp.status_code >= 400:
                raise Exception(
                    f"Supabase signup error: {resp.json() if resp.text else resp.status_code}"
                )
            return resp.json()

    def auth_signin(self, email: str, password: str) -> dict:
        """
        Sign in using email/password via REST.
        Used in /auth/signin.
        """
        url = f"{self.url}/auth/v1/token?grant_type=password"
        payload = {"email": email, "password": password}

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=self._get_headers())
            if resp.status_code >= 400:
                raise Exception(
                    f"Supabase signin error: {resp.json() if resp.text else resp.status_code}"
                )
            return resp.json()

    # ---------- TABLE HELPERS (used by sources.py, rag.py, etc.) ----------

    def table_insert(self, table_name: str, data: dict) -> dict:
        """
        Insert a record into a table.
        Returns inserted row(s). Handles 409 (duplicate) as 'already_exists'.
        """
        url = f"{self.url}/rest/v1/{table_name}"

        with httpx.Client(timeout=self.timeout) as client:
            headers = self._get_headers()
            headers["Prefer"] = "return=representation"
            resp = client.post(url, json=data, headers=headers)

            # 409 = conflict (e.g., unique constraint). For linking tables we often treat this as ok.
            if resp.status_code == 409:
                return {"status": "already_exists"}

            if resp.status_code >= 400:
                raise Exception(
                    f"Insert error [{table_name}]: {resp.json() if resp.text else resp.status_code}"
                )

            return resp.json()

    def table_upsert(self, table_name: str, data: dict, on_conflict: str = "id") -> dict:
        """
        Upsert (insert or update) a record by a conflict key (e.g. id).
        Uses 'resolution=merge-duplicates' so existing rows are merged.
        """
        url = f"{self.url}/rest/v1/{table_name}"

        with httpx.Client(timeout=self.timeout) as client:
            headers = self._get_headers()
            headers["Prefer"] = "resolution=merge-duplicates,return=representation"
            headers["on-conflict"] = on_conflict
            resp = client.post(url, json=data, headers=headers)

            if resp.status_code >= 400:
                raise Exception(
                    f"Upsert error [{table_name}]: {resp.json() if resp.text else resp.status_code}"
                )

            return resp.json()

    def table_select(
        self,
        table_name: str,
        columns: str = "*",
        filters: dict | None = None,
    ) -> list:
        """
        Select rows from a table.
        Example:
            table_select("session_papers", "paper_id,papers(*)", {"session_id": "uuid"})
        """
        url = f"{self.url}/rest/v1/{table_name}?select={columns}"

        if filters:
            for key, value in filters.items():
                url += f"&{key}=eq.{value}"

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._get_headers())
            if resp.status_code >= 400:
                raise Exception(
                    f"Select error [{table_name}]: {resp.json() if resp.text else resp.status_code}"
                )
            return resp.json()


@lru_cache()
def get_supabase() -> SupabaseClient:
    """Singleton SupabaseClient for the app."""
    return SupabaseClient()