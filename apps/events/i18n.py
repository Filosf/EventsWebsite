INTERFACE_TEXT = {
    "ru": {
        "rsvp": "Подтверждение участия",
        "full_name": "ФИО",
        "email": "Электронная почта",
        "phone": "Телефон",
        "attendance": "Вы будете присутствовать?",
        "attending": "Да, буду",
        "declined": "Нет, не смогу",
        "guest_count": "Сколько вас будет?",
        "comment": "Комментарий",
        "submit": "Отправить ответ",
        "closed": "Регистрация закрыта.",
        "thank_you": "Спасибо, ваш ответ сохранён.",
        "back": "Вернуться к мероприятию",
        "max_guests": "Максимальное количество человек: {count}.",
        "duplicate_response": "Ответ от этого гостя уже получен. Для изменения данных обратитесь к организатору.",
        "too_many_requests": "Слишком много попыток отправки. Подождите немного и попробуйте снова.",
        "submission_rejected": "Не удалось отправить ответ. Обновите страницу и попробуйте снова.",
        "submission_too_fast": "Пожалуйста, заполните форму и попробуйте отправить её ещё раз.",
    },
    "en": {
        "rsvp": "RSVP",
        "full_name": "Full name",
        "email": "Email",
        "phone": "Phone",
        "attendance": "Will you attend?",
        "attending": "Yes, I will attend",
        "declined": "No, I cannot attend",
        "guest_count": "How many people will attend?",
        "comment": "Comment",
        "submit": "Submit response",
        "closed": "Registration is closed.",
        "thank_you": "Thank you, your response has been saved.",
        "back": "Back to event",
        "max_guests": "Maximum party size is {count}.",
        "duplicate_response": "A response from this guest already exists. Please contact the organizer to change it.",
        "too_many_requests": "Too many submission attempts. Please wait and try again.",
        "submission_rejected": "The response could not be submitted. Refresh the page and try again.",
        "submission_too_fast": "Please complete the form and try submitting it again.",
    },
    "he": {
        "rsvp": "אישור הגעה",
        "full_name": "שם מלא",
        "email": "דואר אלקטרוני",
        "phone": "טלפון",
        "attendance": "האם תגיעו?",
        "attending": "כן, אגיע",
        "declined": "לא אוכל להגיע",
        "guest_count": "כמה אנשים יגיעו?",
        "comment": "הערה",
        "submit": "שליחת תשובה",
        "closed": "ההרשמה נסגרה.",
        "thank_you": "תודה, תשובתכם נשמרה.",
        "back": "חזרה לאירוע",
        "max_guests": "מספר המשתתפים המרבי הוא {count}.",
        "duplicate_response": "כבר התקבלה תשובה מאורח זה. לשינוי הפרטים יש לפנות למארגן.",
        "too_many_requests": "בוצעו יותר מדי ניסיונות שליחה. יש להמתין ולנסות שוב.",
        "submission_rejected": "לא ניתן היה לשלוח את התשובה. יש לרענן את הדף ולנסות שוב.",
        "submission_too_fast": "יש למלא את הטופס ולנסות לשלוח אותו שוב.",
    },
}

PARTY_SIZE_LABELS = {
    "ru": {
        1: "Буду один",
        2: "Будем вдвоём",
        3: "Будем втроём",
        4: "Нас будет четверо",
        5: "Нас будет пятеро",
        6: "Нас будет шестеро",
        7: "Нас будет семеро",
    },
    "en": {
        1: "I will attend alone",
        2: "There will be two of us",
        3: "There will be three of us",
        4: "There will be four of us",
        5: "There will be five of us",
        6: "There will be six of us",
        7: "There will be seven of us",
    },
    "he": {
        1: "אגיע לבד",
        2: "נהיה שניים",
        3: "נהיה שלושה",
        4: "נהיה ארבעה",
        5: "נהיה חמישה",
        6: "נהיה שישה",
        7: "נהיה שבעה",
    },
}

PARTY_SIZE_FALLBACKS = {
    "ru": "Нас будет {count}",
    "en": "There will be {count} of us",
    "he": "נהיה {count} אנשים",
}


def interface_text(language: str) -> dict:
    return INTERFACE_TEXT.get(language, INTERFACE_TEXT["ru"])


def party_size_choices(language: str, max_additional_guests: int) -> list[tuple[int, str]]:
    selected_language = language if language in PARTY_SIZE_LABELS else "ru"
    labels = PARTY_SIZE_LABELS[selected_language]
    fallback = PARTY_SIZE_FALLBACKS[selected_language]
    maximum_party_size = max(0, max_additional_guests) + 1
    return [
        (party_size - 1, labels.get(party_size, fallback.format(count=party_size)))
        for party_size in range(1, maximum_party_size + 1)
    ]
