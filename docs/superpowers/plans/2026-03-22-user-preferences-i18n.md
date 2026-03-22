# User Preferences & Multi-language Suggestions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store user language/theme preferences in backend metadata, sync across devices on login, and support multi-language welcome suggestions.

**Architecture:** Add `metadata` dict field to User schema/storage. New `PUT /api/auth/profile/metadata` API endpoint for partial updates. Frontend syncs preferences on login from backend and on toggle writes to both localStorage + backend. WELCOME_SUGGESTIONS default becomes a multi-language JSON object keyed by language code.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript (frontend), MongoDB (storage), i18next/react-i18next (i18n)

---

### Task 1: Backend — Add `metadata` field to User schema

**Files:**
- Modify: `src/kernel/schemas/user.py:18-25` (UserBase)
- Modify: `src/kernel/schemas/user.py:81-88` (UserInDB)

- [ ] **Step 1: Add `metadata` to UserBase**

In `src/kernel/schemas/user.py`, add `metadata` field to `UserBase`:

```python
class UserBase(BaseModel):
    """Base user schema."""

    username: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    avatar_url: Optional[str] = None
    oauth_provider: Optional[OAuthProvider] = None
    oauth_id: Optional[str] = None
    metadata: Optional[dict] = None  # User preferences: { language, theme, ... }
```

- [ ] **Step 2: Verify User and UserInDB inherit metadata**

No changes needed — `User` inherits from `UserBase`, `UserInDB` inherits from `User`. The field propagates automatically.

- [ ] **Step 3: Test the schema**

Run: `cd /home/yangyang/LambChat && python -c "from src.kernel.schemas.user import User; u = User(id='1', username='test', email='t@t.com', metadata={'language': 'zh', 'theme': 'dark'}); print(u.metadata)"`
Expected: `{'language': 'zh', 'theme': 'dark'}`

- [ ] **Step 4: Commit**

```bash
git add src/kernel/schemas/user.py
git commit -m "feat(user): add metadata field to User schema for preferences"
```

---

### Task 2: Backend — Add `update_metadata` to UserStorage

**Files:**
- Modify: `src/infra/user/storage.py` (add method after line 571)

- [ ] **Step 1: Add `update_metadata` method**

Add this method to `UserStorage` class in `src/infra/user/storage.py`, after `clear_reset_token`:

```python
async def update_metadata(self, user_id: str, metadata: dict) -> Optional[User]:
    """
    部分更新用户 metadata（merge 方式）

    Args:
        user_id: 用户 ID
        metadata: 要合并的 metadata 字段

    Returns:
        更新后的用户
    """
    from bson import ObjectId

    # Fetch current metadata
    user_dict = await self.collection.find_one({"_id": ObjectId(user_id)})
    if not user_dict:
        from src.kernel.exceptions import NotFoundError
        raise NotFoundError(f"用户 '{user_id}' 不存在")

    current_metadata = user_dict.get("metadata") or {}
    merged = {**current_metadata, **metadata}

    result = await self.collection.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "metadata": merged,
                "updated_at": datetime.now(),
            }
        },
        return_document=True,
    )

    if not result:
        raise NotFoundError(f"用户 '{user_id}' 不存在")

    result["id"] = str(result.pop("_id"))
    return User(**result)
```

- [ ] **Step 2: Verify syntax**

Run: `cd /home/yangyang/LambChat && python -c "from src.infra.user.storage import UserStorage; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/infra/user/storage.py
git commit -m "feat(storage): add update_metadata method for user preferences"
```

---

### Task 3: Backend — Add `PUT /api/auth/profile/metadata` endpoint

**Files:**
- Modify: `src/api/routes/auth/profile.py` (add endpoint and schema)

- [ ] **Step 1: Add request schema and endpoint**

In `src/api/routes/auth/profile.py`, add the request schema after `UsernameUpdateRequest` (after line 38), and the endpoint after `update_username` (after line 157):

```python
class MetadataUpdateRequest(BaseModel):
    """Request schema for updating user metadata (partial merge)"""
    metadata: dict
```

```python
@router.put("/profile/metadata")
async def update_user_metadata(
    request: MetadataUpdateRequest,
    current_user: TokenPayload = Depends(get_current_user_required),
):
    """
    部分更新当前用户 metadata（merge 方式）

    metadata 中的字段会与现有 metadata 合并。
    支持的字段: language (str), theme (str: light/dark)
    """
    from src.infra.user.storage import UserStorage

    storage = UserStorage()

    # Validate language if provided
    supported_languages = {"en", "zh", "ja", "ko", "ru"}
    if "language" in request.metadata:
        lang = request.metadata["language"]
        if lang not in supported_languages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported language: {lang}. Supported: {', '.join(sorted(supported_languages))}",
            )

    # Validate theme if provided
    if "theme" in request.metadata:
        theme = request.metadata["theme"]
        if theme not in ("light", "dark"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid theme: {theme}. Must be 'light' or 'dark'.",
            )

    updated_user = await storage.update_metadata(current_user.sub, request.metadata)
    return updated_user
```

- [ ] **Step 2: Verify syntax**

Run: `cd /home/yangyang/LambChat && python -c "from src.api.routes.auth.profile import router; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/api/routes/auth/profile.py
git commit -m "feat(api): add PUT /api/auth/profile/metadata endpoint"
```

---

### Task 4: Backend — Update WELCOME_SUGGESTIONS default to multi-language

**Files:**
- Modify: `src/kernel/config/definitions.py:22-32`

- [ ] **Step 1: Replace WELCOME_SUGGESTIONS default**

In `src/kernel/config/definitions.py`, replace the `WELCOME_SUGGESTIONS` entry (lines 22-32):

```python
"WELCOME_SUGGESTIONS": {
    "type": SettingType.JSON,
    "category": SettingCategory.FRONTEND,
    "description": "Welcome page suggestions displayed to users (multi-language JSON object keyed by language code)",
    "default": {
        "en": [
            {"icon": "🐍", "text": "Create a Python hello world script"},
            {"icon": "📁", "text": "List files in the workspace directory"},
            {"icon": "📄", "text": "Read the README.md file"},
            {"icon": "🔧", "text": "Help me write a shell script"},
        ],
        "zh": [
            {"icon": "🐍", "text": "创建一个 Python Hello World 脚本"},
            {"icon": "📁", "text": "列出工作区目录中的文件"},
            {"icon": "📄", "text": "读取 README.md 文件"},
            {"icon": "🔧", "text": "帮我写一个 Shell 脚本"},
        ],
        "ja": [
            {"icon": "🐍", "text": "PythonのHello Worldスクリプトを作成"},
            {"icon": "📁", "text": "ワークスペースディレクトリのファイルを一覧表示"},
            {"icon": "📄", "text": "README.mdファイルを読む"},
            {"icon": "🔧", "text": "シェルスクリプトを書くのを手伝って"},
        ],
        "ko": [
            {"icon": "🐍", "text": "Python Hello World 스크립트 만들기"},
            {"icon": "📁", "text": "작업 공간 디렉토리의 파일 목록 보기"},
            {"icon": "📄", "text": "README.md 파일 읽기"},
            {"icon": "🔧", "text": "쉘 스크립트 작성 도와줘"},
        ],
        "ru": [
            {"icon": "🐍", "text": "Создайте скрипт Python Hello World"},
            {"icon": "📁", "text": "Покажите файлы в рабочей директории"},
            {"icon": "📄", "text": "Прочитайте файл README.md"},
            {"icon": "🔧", "text": "Помогите написать скрипт оболочки"},
        ],
    },
    "frontend_visible": True,
},
```

- [ ] **Step 2: Verify syntax**

Run: `cd /home/yangyang/LambChat && python -c "from src.kernel.config.definitions import SETTING_DEFINITIONS; print(len(SETTING_DEFINITIONS['WELCOME_SUGGESTIONS']['default']))"`
Expected: `5` (5 language keys: en, zh, ja, ko, ru)

- [ ] **Step 3: Commit**

```bash
git add src/kernel/config/definitions.py
git commit -m "feat(config): multi-language WELCOME_SUGGESTIONS default"
```

---

### Task 5: Frontend — Update User type with metadata

**Files:**
- Modify: `frontend/src/types/auth.ts:54-64`

- [ ] **Step 1: Add metadata to User interface**

In `frontend/src/types/auth.ts`, update the `User` interface:

```typescript
export interface User {
  id: string;
  username: string;
  email: string;
  avatar_url?: string;
  roles: string[];
  permissions?: string[];
  is_active: boolean;
  metadata?: {
    language?: string;
    theme?: string;
    [key: string]: unknown;
  };
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /home/yangyang/LambChat/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors related to User type

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/auth.ts
git commit -m "feat(types): add metadata field to User interface"
```

---

### Task 6: Frontend — Add `updateMetadata` to auth API

**Files:**
- Modify: `frontend/src/services/api/auth.ts`

- [ ] **Step 1: Add updateMetadata method**

In `frontend/src/services/api/auth.ts`, add this method to the `authApi` object, after `getProfile` (after line 163):

```typescript
/**
 * 更新用户偏好 metadata（部分合并）
 */
async updateMetadata(metadata: Record<string, unknown>): Promise<User> {
  return authFetch<User>(`${API_BASE}/api/auth/profile/metadata`, {
    method: "PUT",
    body: JSON.stringify({ metadata }),
  });
},
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /home/yangyang/LambChat/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api/auth.ts
git commit -m "feat(api): add updateMetadata method to auth API"
```

---

### Task 7: Frontend — Sync preferences on login from backend metadata

**Files:**
- Modify: `frontend/src/hooks/useAuth.tsx`

- [ ] **Step 1: Add metadata sync helper function**

At the top of `frontend/src/hooks/useAuth.tsx`, after the imports (after line 23), add:

```typescript
import i18n from "../i18n";

/** Apply user metadata preferences from backend */
function applyUserMetadata(metadata?: { language?: string; theme?: string }) {
  if (!metadata) return;

  if (metadata.language) {
    localStorage.setItem("language", metadata.language);
    i18n.changeLanguage(metadata.language);
  }

  if (metadata.theme) {
    localStorage.setItem("lamb-agent-theme", metadata.theme);
    if (metadata.theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }
}
```

- [ ] **Step 2: Call applyUserMetadata after fetching user in initAuth**

In `initAuth` (around line 82), after `setUser(currentUser);`, add:

```typescript
applyUserMetadata(currentUser.metadata);
```

- [ ] **Step 3: Call applyUserMetadata after fetching user in login**

In `login` callback (around line 126), after `setUser(currentUser);`, add:

```typescript
applyUserMetadata(currentUser.metadata);
```

- [ ] **Step 4: Call applyUserMetadata after fetching user in handleOAuthCallback**

In `handleOAuthCallback` (around line 190), after `setUser(currentUser);`, add:

```typescript
applyUserMetadata(currentUser.metadata);
```

- [ ] **Step 5: Call applyUserMetadata after fetching user in refreshUser**

In `refreshUser` (around line 222), after `setUser(currentUser);`, add:

```typescript
applyUserMetadata(currentUser.metadata);
```

- [ ] **Step 6: Verify build**

Run: `cd /home/yangyang/LambChat/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/hooks/useAuth.tsx
git commit -m "feat(auth): sync user preferences from metadata on login"
```

---

### Task 8: Frontend — Sync language toggle to backend

**Files:**
- Modify: `frontend/src/components/common/LanguageToggle.tsx`

- [ ] **Step 1: Add backend sync to selectLanguage**

In `frontend/src/components/common/LanguageToggle.tsx`, update `selectLanguage` callback to also call the backend API:

```typescript
const selectLanguage = useCallback(
  (code: string) => {
    i18n.changeLanguage(code);
    localStorage.setItem("language", code);
    setIsOpen(false);
    // Sync to backend (non-blocking)
    authApi.updateMetadata({ language: code }).catch(() => {});
  },
  [i18n],
);
```

Add the import at the top:

```typescript
import { authApi } from "../../services/api";
```

- [ ] **Step 2: Verify build**

Run: `cd /home/yangyang/LambChat/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/common/LanguageToggle.tsx
git commit -m "feat(i18n): sync language preference to backend on toggle"
```

---

### Task 9: Frontend — Sync theme toggle to backend

**Files:**
- Modify: `frontend/src/contexts/ThemeContext.tsx`

- [ ] **Step 1: Add backend sync in theme effect**

In `frontend/src/contexts/ThemeContext.tsx`, add import at top:

```typescript
import { authApi } from "../services/api";
```

In the `useEffect` that applies theme (lines 41-51), add backend sync after `localStorage.setItem`:

```typescript
useEffect(() => {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  localStorage.setItem(STORAGE_KEY, theme);
  // Sync to backend (non-blocking)
  authApi.updateMetadata({ theme }).catch(() => {});
}, [theme]);
```

- [ ] **Step 2: Verify build**

Run: `cd /home/yangyang/LambChat/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/contexts/ThemeContext.tsx
git commit -m "feat(theme): sync theme preference to backend on toggle"
```

---

### Task 10: Frontend — Multi-language welcome suggestions

**Files:**
- Modify: `frontend/src/components/layout/AppContent.tsx:708-714`

- [ ] **Step 1: Update suggestion rendering to use language-keyed lookup**

In `frontend/src/components/layout/AppContent.tsx`, find the WELCOME_SUGGESTIONS rendering (lines 708-714) and replace:

```typescript
{(
  settings?.settings.frontend.find(
    (s) => s.key === "WELCOME_SUGGESTIONS",
  )?.value as
    | Array<{ icon: string; text: string }>
    | undefined
)?.map((suggestion, i) => (
```

With:

```typescript
{(() => {
  const rawValue = settings?.settings.frontend.find(
    (s) => s.key === "WELCOME_SUGGESTIONS",
  )?.value;
  // Support both new multi-language format and legacy flat array
  const currentLang = i18n.language?.split("-")[0] || "en";
  let suggestions: Array<{ icon: string; text: string }> | undefined;
  if (Array.isArray(rawValue)) {
    // Legacy flat array format
    suggestions = rawValue;
  } else if (rawValue && typeof rawValue === "object") {
    // Multi-language format: { en: [...], zh: [...], ... }
    suggestions = rawValue[currentLang] || rawValue["en"];
  }
  return suggestions;
})()?.map((suggestion, i) => (
```

Note: `i18n` is already imported at the top of AppContent.tsx via `useTranslation()`.

- [ ] **Step 2: Verify build**

Run: `cd /home/yangyang/LambChat/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/AppContent.tsx
git commit -m "feat(chat): support multi-language welcome suggestions"
```

---

### Task 11: Frontend — Add i18n keys for Preferences tab

**Files:**
- Modify: `frontend/src/i18n/locales/en.json` (profile section, around line 714)
- Modify: `frontend/src/i18n/locales/zh.json`
- Modify: `frontend/src/i18n/locales/ja.json`
- Modify: `frontend/src/i18n/locales/ko.json`
- Modify: `frontend/src/i18n/locales/ru.json`

- [ ] **Step 1: Add English keys**

In `frontend/src/i18n/locales/en.json`, inside the `"profile"` object (before the closing `}`), add:

```json
"preferences": "Preferences",
"language": "Language",
"theme": "Theme",
"lightTheme": "Light",
"darkTheme": "Dark",
"languageSynced": "Language preference saved",
"themeSynced": "Theme preference saved"
```

- [ ] **Step 2: Add Chinese keys**

In `zh.json`, inside `"profile"`:

```json
"preferences": "偏好设置",
"language": "语言",
"theme": "主题",
"lightTheme": "浅色",
"darkTheme": "深色",
"languageSynced": "语言偏好已保存",
"themeSynced": "主题偏好已保存"
```

- [ ] **Step 3: Add Japanese keys**

In `ja.json`, inside `"profile"`:

```json
"preferences": "設定",
"language": "言語",
"theme": "テーマ",
"lightTheme": "ライト",
"darkTheme": "ダーク",
"languageSynced": "言語設定を保存しました",
"themeSynced": "テーマ設定を保存しました"
```

- [ ] **Step 4: Add Korean keys**

In `ko.json`, inside `"profile"`:

```json
"preferences": "환경설정",
"language": "언어",
"theme": "테마",
"lightTheme": "라이트",
"darkTheme": "다크",
"languageSynced": "언어 환경설정이 저장되었습니다",
"themeSynced": "테마 환경설정이 저장되었습니다"
```

- [ ] **Step 5: Add Russian keys**

In `ru.json`, inside `"profile"`:

```json
"preferences": "Настройки",
"language": "Язык",
"theme": "Тема",
"lightTheme": "Светлая",
"darkTheme": "Тёмная",
"languageSynced": "Настройки языка сохранены",
"themeSynced": "Настройки темы сохранены"
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/i18n/locales/
git commit -m "feat(i18n): add preference tab translations for all languages"
```

---

### Task 12: Frontend — Create ProfilePreferencesTab component

**Files:**
- Create: `frontend/src/components/profile/tabs/ProfilePreferencesTab.tsx`

- [ ] **Step 1: Create the Preferences tab component**

Create `frontend/src/components/profile/tabs/ProfilePreferencesTab.tsx`:

```typescript
import { useTranslation } from "react-i18next";
import { Languages, Sun, Moon } from "lucide-react";
import { useTheme } from "../../../contexts/ThemeContext";

const LANGUAGES = [
  { code: "en", nativeName: "English" },
  { code: "zh", nativeName: "中文" },
  { code: "ja", nativeName: "日本語" },
  { code: "ko", nativeName: "한국어" },
  { code: "ru", nativeName: "Русский" },
];

export function ProfilePreferencesTab() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();

  const handleLanguageChange = (code: string) => {
    i18n.changeLanguage(code);
    localStorage.setItem("language", code);
    authApi.updateMetadata({ language: code }).catch(() => {});
  };

  const handleThemeChange = (newTheme: "light" | "dark") => {
    setTheme(newTheme);
    authApi.updateMetadata({ theme: newTheme }).catch(() => {});
  };

  return (
    <div className="space-y-3">
      {/* Language */}
      <div className="rounded-xl bg-gray-50 dark:bg-stone-700/50 p-3.5 sm:p-4">
        <div className="flex items-center gap-2 mb-3">
          <Languages size={16} className="text-gray-500 dark:text-stone-400" />
          <h4 className="font-medium text-sm text-gray-900 dark:text-stone-100">
            {t("profile.language")}
          </h4>
        </div>
        <div className="flex flex-wrap gap-2">
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => handleLanguageChange(lang.code)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                i18n.language === lang.code
                  ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
                  : "bg-white dark:bg-stone-600/50 text-gray-600 dark:text-stone-300 border border-gray-200 dark:border-stone-600 hover:bg-gray-100 dark:hover:bg-stone-600"
              }`}
            >
              {lang.nativeName}
            </button>
          ))}
        </div>
      </div>

      {/* Theme */}
      <div className="rounded-xl bg-gray-50 dark:bg-stone-700/50 p-3.5 sm:p-4">
        <div className="flex items-center gap-2 mb-3">
          {theme === "dark" ? (
            <Moon size={16} className="text-gray-500 dark:text-stone-400" />
          ) : (
            <Sun size={16} className="text-gray-500 dark:text-stone-400" />
          )}
          <h4 className="font-medium text-sm text-gray-900 dark:text-stone-100">
            {t("profile.theme")}
          </h4>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleThemeChange("light")}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
              theme === "light"
                ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
                : "bg-white dark:bg-stone-600/50 text-gray-600 dark:text-stone-300 border border-gray-200 dark:border-stone-600 hover:bg-gray-100 dark:hover:bg-stone-600"
            }`}
          >
            <Sun size={14} />
            {t("profile.lightTheme")}
          </button>
          <button
            onClick={() => handleThemeChange("dark")}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
              theme === "dark"
                ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
                : "bg-white dark:bg-stone-600/50 text-gray-600 dark:text-stone-300 border border-gray-200 dark:border-stone-600 hover:bg-gray-100 dark:hover:bg-stone-600"
            }`}
          >
            <Moon size={14} />
            {t("profile.darkTheme")}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/yangyang/LambChat/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors (fix any import issues)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/profile/tabs/ProfilePreferencesTab.tsx
git commit -m "feat(profile): create ProfilePreferencesTab component"
```

---

### Task 13: Frontend — Add Preferences tab to ProfileModal

**Files:**
- Modify: `frontend/src/components/profile/ProfileModal.tsx`

- [ ] **Step 1: Import ProfilePreferencesTab**

In `frontend/src/components/profile/ProfileModal.tsx`, add import (after line 10):

```typescript
import { ProfilePreferencesTab } from "./tabs/ProfilePreferencesTab";
```

- [ ] **Step 2: Update tab type union**

Change line 24-26 from:

```typescript
const [activeTab, setActiveTab] = useState<
  "info" | "password" | "notification" | "agent"
>("info");
```

To:

```typescript
const [activeTab, setActiveTab] = useState<
  "info" | "password" | "notification" | "agent" | "preferences"
>("info");
```

- [ ] **Step 3: Add tab entry**

In the `tabs` array (line 57-62), add:

```typescript
{ key: "preferences", label: t("profile.preferences") },
```

- [ ] **Step 4: Add tab content rendering**

In the tab content section (after line 122), add:

```typescript
{activeTab === "preferences" && <ProfilePreferencesTab />}
```

- [ ] **Step 5: Verify build**

Run: `cd /home/yangyang/LambChat/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/profile/ProfileModal.tsx
git commit -m "feat(profile): add Preferences tab to ProfileModal"
```

---

### Task 14: Full build verification

**Files:** None (verification only)

- [ ] **Step 1: Run frontend build**

Run: `cd /home/yangyang/LambChat/frontend && npm run build 2>&1 | tail -20`
Expected: Build succeeds with no errors

- [ ] **Step 2: Run backend verification**

Run: `cd /home/yangyang/LambChat && python -c "from src.api.routes.auth.profile import router; from src.kernel.schemas.user import User; from src.infra.user.storage import UserStorage; print('All backend imports OK')"`
Expected: `All backend imports OK`

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address build issues from review"
```
