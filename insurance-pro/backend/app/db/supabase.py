import httpx
from typing import Dict, Any, Optional, List, Union
from supabase import create_client, Client
from app.core.config import settings

# Primary Supabase Client (Service Role for backend operations & administrative tasks)
supabase_admin: Client = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY
)

# Public Supabase Client (Anon Key for user auth operations like sign_in_with_password)
supabase_public: Client = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_ANON_KEY
)


class AsyncSupabaseDB:
    """
    High-performance, non-blocking Async PostgREST client wrapper
    built with HTTPX to guarantee async/await compliance in FastAPI workers.
    """
    def __init__(self):
        self.base_url = f"{settings.SUPABASE_URL}/rest/v1"
        self.storage_url = f"{settings.SUPABASE_URL}/storage/v1"
        self.headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self.headers, timeout=15.0)

    async def select(
        self, 
        table: str, 
        params: Optional[Dict[str, str]] = None,
        single: bool = False
    ) -> Any:
        async with self._get_client() as client:
            headers = dict(self.headers)
            if single:
                headers["Accept"] = "application/vnd.pgrst.object+json"
            response = await client.get(f"{self.base_url}/{table}", params=params, headers=headers)
            if response.status_code >= 400:
                return None if single and response.status_code == 406 else response.json()
            return response.json()

    async def insert(self, table: str, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Any:
        async with self._get_client() as client:
            response = await client.post(f"{self.base_url}/{table}", json=data)
            if response.status_code >= 400:
                raise Exception(f"Insert error into {table}: {response.text}")
            return response.json()

    async def update(self, table: str, filters: Dict[str, str], data: Dict[str, Any]) -> Any:
        async with self._get_client() as client:
            response = await client.patch(f"{self.base_url}/{table}", params=filters, json=data)
            if response.status_code >= 400:
                raise Exception(f"Update error in {table}: {response.text}")
            return response.json()

    async def delete(self, table: str, filters: Dict[str, str]) -> Any:
        async with self._get_client() as client:
            response = await client.delete(f"{self.base_url}/{table}", params=filters)
            if response.status_code >= 400:
                raise Exception(f"Delete error in {table}: {response.text}")
            return response.json()

    async def create_signed_upload_url(
        self, 
        bucket: str, 
        file_path: str, 
        expires_in: int = 900
    ) -> Dict[str, Any]:
        """
        Generate short-lived signed upload URL directly from Supabase Storage API.
        Enables clients to stream up to 100MB files directly without buffering through FastAPI.
        """
        endpoint = f"{self.storage_url}/object/upload/sign/{bucket}/{file_path}"
        async with self._get_client() as client:
            res = await client.post(endpoint, json={"expiresIn": expires_in})
            if res.status_code >= 400:
                try:
                    sdk_res = supabase_admin.storage.from_(bucket).create_signed_upload_url(file_path)
                    return {
                        "signed_url": sdk_res.get("signed_url") or sdk_res.get("url"),
                        "token": sdk_res.get("token", ""),
                        "path": file_path
                    }
                except Exception as sdk_err:
                    raise Exception(f"Storage signed URL creation failed: {res.text} | SDK error: {str(sdk_err)}")
            
            data = res.json()
            raw_url = data.get("url") or data.get("signedURL") or data.get("signed_url")
            full_url = f"{settings.SUPABASE_URL}/storage/v1{raw_url}" if raw_url and raw_url.startswith("/") else raw_url
            return {
                "signed_url": full_url or f"{settings.SUPABASE_URL}/storage/v1/object/{bucket}/{file_path}",
                "token": data.get("token", ""),
                "path": file_path
            }


db = AsyncSupabaseDB()