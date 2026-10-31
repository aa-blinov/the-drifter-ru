# Рабочий процесс локализации The Drifter

Этот файл дополняет `SKILL.md` командами и ограничениями конкретного
репозитория. Если команда изменилась, сверь её с `AGENTS.md` и самим файлом,
прежде чем запускать.

## Источники и файлы

- `corpus/english.csv` — английский корпус с ключами `(Character, ID)`, файлом
  сценария и функцией источника. Извлечён из копии игры, совпадает с ней
  построчно.
- `translation/Russian/translation.csv` — файл, который читает игра.
- `src/voice/glossary.json` — закреплённые термины и имена.
- `src/voice/bible.md` — голос редактора; тот же текст в
  `docs/style-guide.md`.
- `src/voice/manual_fixes.json` — правки, которые должны сохраниться при
  сборке.
- `src/voice/allowed_latin.json` — слова, которые остаются на латинице.
- `docs/layout.md` — ширина русской строки, измеренная по шрифтам игры.

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
python -m src.drru.translate --stage manual --source work/corpus/polish.jsonl --out work/corpus/final.jsonl
```

4. Проверь текст и правила:

```bash
python -m unittest discover -s tests -v
python -m src.drru.qa.py
python scripts/check_terms.py
python scripts/check_fixes.py
python scripts/scan_ai_patterns.py
```

## Полный прогон пайплайна

```bash
python src/drru/extract_corpus.py --game "<путь к The Drifter>"
python src/drru/translate.py --stage bulk
python src/drru/translate.py --stage editorial
python src/drru/canonicalise.py
python src/drru/typography.py
python src/drru/polish.py
python src/drru/proofread.py
python src/drru/translate.py --stage manual
python src/drru/qa.py
python src/drru/build.py
```

Стадии пишут `work/corpus/*.jsonl`, и каждая читает файл, который написала
предыдущая: `bulk` → `edit` → `canon` → `typo` → `polish` → `final`. Сборка
читает `final`.

Прогон вызывает модель и читает адрес эндпоинта из окружения: `DRRU_BASE_URL`
(по умолчанию `http://127.0.0.1:8788/v1`) и `DRRU_MODEL` (по умолчанию
`minimax-m3`). Кэш ответов — в `work/cache/`; прерванный прогон
продолжается без повторной траты.

Полный прогон не заменяет одну ручную правку: для неё достаточно
`--stage manual`.

## Вычитка

Сканер ИИ-паттернов ищет следы машинного письма, а не ошибки перевода:

```bash
python scripts/scan_ai_patterns.py --verbose
```

Совпадение — это строка для чтения, а не приговор: английский источник рядом
показывает, пришло ли слово из игры или из перевода.

Ошибку перевода ищет вычитка против источника:

```bash
python -m src.drru.proofread.py
```

Она читает каждую строку перевода рядом с её английским источником и
называет расхождения: изменённый смысл, потерянный факт, оставленное
английское слово, обрыв фразы, посторонний алфавит. Каждое её замечание
читается до правки: модель — детектор, а не authority.

Правка попадает в два места: в `translation/Russian/translation.csv` и в
`src/voice/manual_fixes.json`. Второе — то, что переживает следующий прогон.
`scripts/check_fixes.py` проверяет, что правка не потеряла источник: ни
плейсхолдера, ни числа, ни предложения.

## Терминология и глоссарий

Терминология проверяется по тексту, а не по списку:

```bash
python scripts/check_terms.py
```

Читает строки, где термин встречается в источнике, и называет те, где у
термина две русские формы. Падежные формы дефектом не считаются: «Рот»,
«Рота» и «Ротом» — одно слово.

Пополнить глоссарий и привести документ в порядок:

```bash
python scripts/build_glossary.py      # термины источника, которых нет в глоссарии
python scripts/glossary_expand.py     # русская форма термина по строкам, где он встречается
python scripts/render_glossary.py     # docs/glossary.md из src/voice/glossary.json
```

## Установка и экранная проверка

```powershell
$env:DR_GAME_DIR = 'S:\SteamLibrary\steamapps\common\The Drifter'
python scripts/fetch_fonts.py
python scripts/install.py --game $env:DR_GAME_DIR --dry-run
python scripts/install.py --game $env:DR_GAME_DIR
```

Установщик:

1. копирует `translation.csv` в каталог игры;
2. сохраняет оригинальный `sharedassets1.assets` в `_ru_backup/`;
3. патчит ассеты побайтно и проверяет результат перед заменой.

Проверка в игре:

```bash
python scripts/screenshot.py --out work/shots/scene.png   # снимок окна игры
python scripts/click.py --at 960,515                       # клик в игре
python scripts/send_keys.py --keys "{ENTER}"                # ввод в игре
```

Игра читает `translation.csv` при старте. Язык выбирается в **Options →
Language → Русский**.

## Чего здесь нельзя проверить

- **Перенос строки в самой узкой панели.** Ширина панели в пикселях в
  шрифтах не хранится. Измерено то, что можно: русский текст занимает не
  больше места, чем английский.
- **Вычитка носителем языка.** Перевод прошёл автоматические проверки,
  вычитку против источника и проверку в игре. То, что может проверить только
  живой читатель, не проверялось.

## Pull request и выпуск

Следуй `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE.md` и
`docs/release-process.md`. Не коммить, не пушь, не сливай PR и не создавай
тег релиза без прямой просьбы пользователя.
