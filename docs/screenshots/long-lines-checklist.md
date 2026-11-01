# Визуальная проверка длинных строк

Эти 15 строк стали длиннее после прохода по голосу перевода. Общие кадры
сцены у костра и реплики `Mick|1445` подтверждают работу шрифтов, но не
закрывают проверку этих ключей: каждый нужно увидеть в своей сцене.

Для каждого пункта открой указанную сцену в игре `v1.1.5` с русским языком,
проверь обрезку, перенос, базовую линию и влезание в панель. Если строка
помещается, приложи кадр и отметь пункт. Если нет — сначала исправь перевод,
обнови CSV и `src/voice/manual_fixes.json`, затем повтори установку и проверку.

- [ ] `Roth|44` — `Room- LabRoom`, `Look at Roth's shelves while he's here`.
- [ ] `Sarah|70` — `Room- Kitchen`, `Answering machine msg from Sister's Husband Joe`.
- [ ] `Nazari|99` — `Dialog- DrTalks`, `OptionTopicCeo`.
- [ ] `|1718` — `Dialog- CeoLab`, `OptionTopicLooping`.
- [ ] `Narr|6` — `Room- BoxCar`, `WakeUp`.
- [ ] `|1299` — `Item- TopicPhone`, `Item Description`.
- [ ] `Roth|133` — `Room- EscInterface`, `Pull gun on Roth`.
- [ ] `|783` — `Room- LabInterface`, `OnEnterRoom`.
- [ ] `Narr|1657` — `Room- LabReactor`, `Look at reactor, see it measures Rads, maybe should check geiger counter`.
- [ ] `Narr|878` — `Room- Hospital`, `Call button- Notice handcuffs`.
- [ ] `Mick|48` — `Room- Bridge`, `Show bill the jerrycan`.
- [ ] `Narr|2128` — `Item- Blower`, `OnUseInvInventory`.
- [ ] `Roth|343` — `Dialog- CeoLab`, `OptionTopicMalingee`.
- [ ] `Klein|101` — `Room- End`, `Signal helicopter`.
- [ ] `Mick|905` — `Room- LabInterface`, `Use heal cartridge on machine console`.

Текущий загруженный сейв открывает сцену у моста, но в доступных ячейках
инвентаря нет канистры, поэтому `Mick|48` пока не удалось вызвать. Остальные
сцены находятся в других главах. Сейв и настройки были восстановлены после
пробного прохода; их исходные SHA-256 сохранены в рабочем журнале задачи.
