import httpx
from typing import Optional
from datetime import datetime, timedelta
import random

from app.config import get_settings
from app.models.schemas import VehicleStatus

settings = get_settings()


class ValidationAPIClient:
    """
    Async client for external vehicle validation API.
    Checks road tax and insurance status for vehicles.
    """
    
    def __init__(self):
        self._base_url = settings.external_api_url
        self._timeout = settings.external_api_timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout
            )
        return self._client
    
    async def check_vehicle(self, plate_number: str) -> VehicleStatus:
        """
        Check vehicle's road tax and insurance status.
        
        Args:
            plate_number: The vehicle's plate number
            
        Returns:
            VehicleStatus with tax and insurance information
        """
        try:
            client = await self._get_client()
            response = await client.get(f"/vehicle/{plate_number}")
            
            if response.status_code == 200:
                data = response.json()
                return VehicleStatus(
                    plate_number=plate_number,
                    owner_name=data.get("owner_name"),
                    owner_id=data.get("owner_id"),
                    road_tax_valid=data.get("road_tax_valid", True),
                    road_tax_expiry=data.get("road_tax_expiry"),
                    insurance_valid=data.get("insurance_valid", True),
                    insurance_expiry=data.get("insurance_expiry")
                )
            elif response.status_code == 404:
                # Vehicle not found in system - assume compliant (new vehicle)
                return VehicleStatus(
                    plate_number=plate_number,
                    road_tax_valid=True,
                    insurance_valid=True
                )
            else:
                # API error - return error status
                raise Exception(f"API returned status {response.status_code}")
                
        except httpx.RequestError as e:
            # Network error - use mock data for demo
            print(f"⚠️ External API unavailable: {e}")
            print("📝 Using mock data for demo...")
            return await self._get_mock_status(plate_number)
    
    async def notify_fine(self, plate_number: str, fine_amount: float, fine_type: str) -> bool:
        """
        Notify external system about issued fine.
        
        Args:
            plate_number: The vehicle's plate number
            fine_amount: Amount of the fine
            fine_type: Type of violation
            
        Returns:
            True if notification was successful
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/fines",
                json={
                    "plate_number": plate_number,
                    "fine_amount": fine_amount,
                    "fine_type": fine_type,
                    "issued_at": datetime.now().isoformat()
                }
            )
            return response.status_code in (200, 201)
        except httpx.RequestError:
            # Log but don't fail - fine is still recorded locally
            print(f"⚠️ Could not notify external API about fine for {plate_number}")
            return False
    
    async def _get_mock_status(self, plate_number: str) -> VehicleStatus:
        """
        Generate mock vehicle status for demo/testing.
        Uses deterministic randomization based on plate number.
        """
        # Use plate number hash for deterministic results
        seed = sum(ord(c) for c in plate_number)
        random.seed(seed)
        
        # 60% chance of being compliant
        is_tax_valid = random.random() < 0.6
        is_insurance_valid = random.random() < 0.7
        
        # Generate mock owner info
        mock_names = [
            "Ahmad bin Abdullah", "Tan Wei Ming", "Siti Nurhaliza",
            "Raj Kumar", "Lee Chong Wei", "Maria Gonzales",
            "Wong Kar Wai", "Fatimah binti Hassan", "Chen Xiaoming"
        ]
        
        mock_name = mock_names[seed % len(mock_names)]
        mock_id = f"{''.join(str((seed * 7 + i) % 10) for i in range(12))}"
        
        # Generate expiry dates
        now = datetime.now()
        if is_tax_valid:
            tax_expiry = now + timedelta(days=random.randint(30, 365))
        else:
            tax_expiry = now - timedelta(days=random.randint(1, 180))
        
        if is_insurance_valid:
            insurance_expiry = now + timedelta(days=random.randint(30, 365))
        else:
            insurance_expiry = now - timedelta(days=random.randint(1, 180))
        
        return VehicleStatus(
            plate_number=plate_number,
            owner_name=mock_name,
            owner_id=mock_id,
            road_tax_valid=is_tax_valid,
            road_tax_expiry=tax_expiry,
            insurance_valid=is_insurance_valid,
            insurance_expiry=insurance_expiry
        )
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Global validation API client instance
validation_api = ValidationAPIClient()

