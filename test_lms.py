"""Дымовой тест: ходит в живую ЛМС с кукой из .env. Запуск: python test_lms.py"""

import server as s


def main() -> None:
    sched = s.schedule(limit=5)
    assert "\n" in sched or sched.startswith("Занятий"), sched
    print("schedule OK\n ", sched.splitlines()[0])

    cur = s.courses()
    assert "текущий" in cur, cur[:200]
    ids = [l.split("]")[0].strip("[") for l in cur.splitlines() if l.startswith("[")]
    assert ids, cur
    print("courses OK  ", len(ids), "дисциплин")

    first_course_id = ids[0]
    detail = s.course(first_course_id)
    assert "Задания и контрольные мероприятия" in detail, detail[:300]
    events = [l.split("]")[0].strip("[") for l in detail.splitlines() if l.startswith("[")]
    assert events, detail
    print("course OK   ", len(events), "мероприятий")

    task = s.assignment(events[0])
    assert "Описание" in task, task[:300]
    print("assignment OK\n ", task.splitlines()[0])

    g = s.grades()
    assert "ЗАЧЁТНАЯ КНИЖКА" in g and "Семестр" in g, g[:300]
    print("grades OK   ", len(g.splitlines()), "строк")

    assert s.notifications()
    assert s.messages()
    print("notifications + messages OK")

    assert "Семестр" in s.curriculum()
    assert "Оплачено" in s.finance() or "Итого" in s.finance()
    assert s.announcements()
    assert s.dialog("curator")
    assert s.dialog("zzz").startswith("kind бывает")
    assert s.schedule(limit=3, kind="webinar")
    print("curriculum + finance + announcements + dialog + webinars OK")

    # confirm=False обязан только показать план и ничего не отправить
    dry = s.submit_assignment(events[0], text="проверка", confirm=False)
    assert "НЕ ОТПРАВЛЕНО" in dry, dry
    assert "нет ни файла, ни текста" in s.submit_assignment(events[0])
    assert "Файла нет" in s.submit_assignment(events[0], file_path="нет-такого.docx")
    print("submit_assignment dry-run OK (ничего не отправлено)")


if __name__ == "__main__":
    main()
    print("\nвсё зелёное")
