# Рабочий процесс локализации The Drifter

Этот файл дополняет `SKILL.md` командами и ограничениями конкретного
репозитория. Если команда изменилась, сверь её с `AGENTS.md` и самим файлом,
прежде чем запускать.

## Источники и файлы

- `corpus/english.csv` — английский корпус с ключами `(Character, ID)`,
  файлом сценария и функцией источника.
- `translation/Russian/translation.csv` — файл, который читает игра.
- `src/voice/glossary.json` — закреплённые термины и имена.
- `src/voice/bible.md` — голос редактора; тот же текст в
  `docs/style-guide.md`.
- `src/voice/manual_fixes.json` — правки, которые должны сохраниться при
  сборке.
- `docs/layout.md` — что известно о ширине русской строки и что не измерено.
- `tests/test_translation.py` — проверки файла, который читает игра.

Сначала найди английский источник и проверь его повторы:

```bash
rg -n "KEY_NAME" corpus src/voice docs
```

Не считай строку переведённой, пока не подтвердил, что она есть в
`translation/Russian/translation.csv` с тем же ключом.

## Ручная правка

1. Исправь ячейку в `translation/Russian/translation.csv`.
2. Внеси тот же вариант в `src/voice/manual_fixes.json` под ключом
   `Character|ID`.
3. Примени сохранённые правки:

```bash
python -m src.drru.translate --stage manual
```

4. Проверь тесты и текстовые правила:

```bash
python -m unittest discover -s tests -v
python src/drru/qa.py
```

## Полный прогон пайплайна

```bash
python src/drru/extract_corpus.py --game "<путь к The Drifter>"
python src/drru/translate.py --stage bulk
python src/drru/translate.py --stage editorial
python src/drru/translate.py --stage manual
python src/drru/canonicalise.py
python src/drru/typography.py
python src/drru/polish.py
python src/drru/repair.py
python src/drru/translate.py --stage manual
python src/drru/qa.py
python src/drru/build.py
```

Прогон вызывает модель и читает адрес эндпоинта из окружения: `DRRU_BASE_URL`
(по умолчанию `http://127.0.0.1:8788/v1`) и `DRRU_MODEL` (по умолчанию
`minimax-m3`). Кэш ответов — в `work/cache/`; прерванный прогон
продолжается без повторной траты.

Полный прогон не заменяет одну ручную правку: для неё достаточно
`--stage manual`.

## Установка и экранная проверка

```powershell
$env:EB_GAME_DIR = 'C:\Program Files (x86)\Steam\steamapps\common\The Drifter'
python scripts/fetch_fonts.py
python scripts/install.py --game $env:EB_GAME_DIR --dry-run
python scripts/install.py --game $env:EB_GAME_DIR
```

Проверь полный путь до запуска: установщик удаляет и создаёт заново папку
`_ru_backup` рядом с `TheDrifter.exe`, пишет `translation.csv` в каталог игры
и переписывает `TheDrifter_Data/sharedassets1.assets`. Оригинальный ассет
копируется в `_ru_backup` перед первой правкой.

Игра читает CSV при старте. Язык выбирается в **Options → Language →
Русский**; `V` и `B` переключают языки на лету.

## Чего здесь нельзя проверить

В этом репозитории нет копии игры, поэтому не измерена ширина русской строки
в панели и не снят скриншот игры на русском. Не пиши, что перевод проверен
в игре, если проверен только исходный текст. `docs/layout.md` говорит об
этом прямо.

## Pull request и выпуск

Следуй `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE.md` и
`docs/release-process.md`. Не коммить, не пушь, не сливай PR и не создавай
тег релиза без прямой просьбы пользователя.
