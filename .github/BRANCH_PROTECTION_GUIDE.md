# Branch Protection — Автоматическая настройка

Защита веток применяется через скрипт + JSON-конфиг, без ручной возни в GitHub UI.

## Файлы

| Файл | Назначение |
|------|-----------|
| `.github/branch_protection.json` | Конфиг правил для `main` и `develop` |
| `.github/apply_branch_protection.py` | Скрипт применения через GitHub API |

## Получить Personal Access Token (PAT)

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. **Generate new token (classic)**
3. Scope: `repo` (для публичного репо достаточно `public_repo`)
4. Скопировать токен — он показывается **один раз**

## Применить защиту

```bash
python .github/apply_branch_protection.py --token ghp_xxxxxxxxxxxxxxxxxxxx
```

Ожидаемый вывод:
```
Applying branch protection for: Shugar86/additive-light
  [OK] main: protection applied
  [OK] develop: protection applied

All branches protected successfully.
```

## Что применяется

### `main` — строгая защита
- Требуется **1 approve** в PR перед мержем
- Stale reviews сбрасываются при новых коммитах
- Правила применяются **в том числе к администраторам** (`enforce_admins: true`)
- Force push и удаление ветки **запрещены**

### `develop` — стандартная защита
- Требуется **1 approve** в PR перед мержем
- Администраторы могут пушить напрямую (для хотфиксов)
- Force push и удаление ветки **запрещены**

## Изменить правила

Отредактируй `branch_protection.json` и перезапусти скрипт.  
Полная схема полей: [GitHub Docs — Branch Protection API](https://docs.github.com/en/rest/branches/branch-protection)
