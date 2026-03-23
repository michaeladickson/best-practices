# Pydantic & Data Model Patterns

## Settings Management

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore"
    )
    environment: str = "development"
    api_key: SecretStr = SecretStr("")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- Single cached settings object per process
- `SecretStr` for API keys prevents accidental logging
- `extra="ignore"` avoids errors from extra env vars
- `.env` in dev, env vars in prod

## API Models (Pydantic)

```python
class DailySalesData(BaseModel):
    store_id: str
    business_date: date
    gross_sales: Decimal
    net_sales: Decimal
    payments: PaymentBreakdown = Field(default_factory=PaymentBreakdown)

    @model_validator(mode="after")
    def compute_derived(self) -> "DailySalesData":
        if self.average_ticket is None and self.transaction_count > 0:
            self.average_ticket = (self.net_sales / self.transaction_count).quantize(Decimal("0.01"))
        return self
```

- Use `Decimal` for financial fields
- `Field(default_factory=...)` for mutable defaults
- `@model_validator(mode="after")` for computed fields

## Internal Models (Dataclasses)

```python
@dataclass
class Classification:
    category: str
    priority: str
    sentiment: str
    summary: str
    confidence: float
```

Use dataclasses (not Pydantic) for internal domain models that don't need serialization/validation.

## TypeScript Types (Frontend/Mobile)

```typescript
// Use string unions, not enums
type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack';

interface FoodLog {
  id: string;
  user_id: string;
  meal_type: MealType;
  items: FoodItem[];        // JSONB in DB
  total_calories: number;
  source: 'voice' | 'manual' | 'photo';
  healthkit_uuid?: string;  // Optional external ID for dedup
}
```

- Prefer string unions over TypeScript enums
- Include `source` field for data provenance
- Keep types colocated in a single `types/index.ts`

## Where Used

- **crumbl-ops**: Pydantic for API + Settings, dataclasses for internal
- **wealth-mgmt**: Pydantic Settings, manual CSV parsing
- **healthpulse**: TypeScript interfaces in `types/index.ts`
