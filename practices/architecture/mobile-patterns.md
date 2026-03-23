# Mobile / React Native Patterns

## Expo Router Navigation

```
app/
  _layout.tsx           # Root: AuthProvider + StatusBar
  (auth)/
    login.tsx           # Login screen
  (tabs)/
    _layout.tsx         # Tab navigator
    dashboard.tsx
    food.tsx
    workouts.tsx
    settings.tsx
```

- Wrap `AuthProvider` at root level
- Conditional routing: loading → login → authenticated tabs
- Use Expo Router groups for logical screen organization

## Platform-Specific Files

Use file extensions for platform branching:
```
lib/
  healthkit.native.ts   # iOS HealthKit implementation
  healthkit.web.ts      # Web stub/mock
```

Metro auto-resolves based on `Platform.OS`. Cleaner than runtime conditionals.

## Three-Phase Data Sync

1. **Backfill** (first launch): 90 days of historical data, parallel fetches
2. **Incremental** (subsequent launches): since last sync timestamp, 7-day fallback
3. **Live Observers** (while active): debounced (3s) subscription-based updates

```typescript
interface SyncState {
  backfillComplete: boolean;
  lastSyncTimestamp: string | null;
  anchors: { workouts, sleep, heartRate, ... }
}
// Persisted in AsyncStorage
```

## Dev Mode Flags

```typescript
const DEV_BYPASS_AUTH = __DEV__ && false;  // Skip auth for testing
const DEV_MOCK = __DEV__ && false;         // Return mock data
```

Always default to `false`. Document flag locations in CLAUDE.md.

## Component Pattern

```typescript
interface Props {
  title: string;
  isProcessing: boolean;
  onSubmit: (value: string) => void;
  onCancel: () => void;
  preview?: React.ReactNode;
}
```

- Conditional imports with try-catch for optional native modules
- Branch UI on `Platform.OS` and capability checks
- Register hooks only when the native module is available
- Always provide fallback UI for web

## Supabase Client (Platform-Aware Storage)

```typescript
if (Platform.OS === 'web') {
  // Simple in-memory Map
} else {
  // Encrypted AsyncStorage + SecureStore with AES-256-CTR
}
```

## Dark Theme

- Enforce in app.json: `"userInterfaceStyle": "dark"`
- Centralize colors in `constants/index.ts`
- All components reference `COLORS.background`, `COLORS.text`, etc.

## Where Used

- **healthpulse**: Full Expo Router + HealthKit + Supabase mobile app
