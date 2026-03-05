# Настройка защиты веток (1 раз владельцу репозитория)

Эта настройка **нужна только один раз** в самом начале проекта, чтобы случайно не запушить сломанный код напрямую в `main` или `develop`.  
Делает это **только Shugar86** (как создатель репозитория). Коллеге ничего делать не нужно.

## Шаги (занимает 1 минуту):

1. Открой GitHub: [Настройки веток репозитория](https://github.com/Shugar86/additive-light/settings/branches)
2. Нажми кнопку **"Add branch ruleset"** (или "Add rule")
3. Заполни форму для ветки `main`:
   * **Rule name**: `main`
   * **Target branches**: `Add target -> Include by pattern -> main`
   * Поставь галочки:
     * ✅ **Require a pull request before merging** 
     * ✅ **Require approvals (1)**
     * ✅ **Block force pushes**
     * ✅ **Block deletions**
4. Нажми **"Create"** или **"Save"** внизу.
5. Повтори шаги 2-4 для ветки `develop`:
   * **Rule name**: `develop`
   * **Target branches**: `Add target -> Include by pattern -> develop`
   * ✅ **Require a pull request before merging** 
   * ✅ **Require approvals (1)**

Всё! Теперь никто из вас двоих (даже случайно) не сможет запушить что-то прямо в `main` или `develop` минуя Pull Request. Коллеге про это думать не надо, он просто работает в своих ветках `feature/*`.