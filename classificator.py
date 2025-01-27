import pandas as pd

def determine_label(row):
    incassators = [
        "ЗаменаКассеты",
        "ЗаполнениеКассеты"
    ]

    mechanic = [
        "ЗажеваннаяКупюра",
        "ЗагрузкаПроцессораВысокая",
        "ОжиданиеПользователя",
        "АварийноеВыключение",
        "ОшибкаОбновления",
        "ОшибкаПечати",
        "ОшибкаПриемаКупюр",
        "ОшибкаКарт",
        "ОшибкаВыдачиНаличности",
        "ОшибкаТехническая",
        "ОшибкаЖесткогоДиска",
        "ОтказВОбслуживании",
        "СигнализацияОшибки",
        "ОбслуживаниеТребуется",
        "ОшибкаСинхронизацииДанных",
        "ОшибкаСети",
        "ПроблемаСоСвязью"
    ]

    all_good = [
        "ВосстановлениеСвязи",
        "ВыходПользователя",
        "ПроверкаБаланс",
        "ОбработкаЗапроса",
        "СнятиеНаличными",
        "ВнесениеНаличных",
        "ВходПользователя",
        "ПроверкаЖесткогоДиска",
        "ПерезагрузкаУстройства"
    ]

    chek_need = [
        "СостояниеКартриджа",
        "СостояниеПриемаКупюр",
        "Предупреждение",
        "ПроверкаСостоянияКлавиатуры",
        "ПроверкаСостоянияКарт",
        "ПроверкаЭнергоснабжения",
        "ОбновлениеПрограммногоОбеспечения",
        "ТестированиеУстройства",
        "СостояниеУстройстваИзменено",
        "ПроверкаКассеты",
        "ОбновлениеБезопасности",
        "ЗавершениеТранзакции",
        "ПроверкаОбновлений",
        "ПроверкаСистемныхЛогов",
        "ТестированиеСистемы",
        "УстановкаОбновлений",
        "ПроверкаСостоянияСвязи",
        "ПроверкаСостоянияПечати"
    ]

    incassator_values = [
        'Низкий уровень наличных',
        'Нет наличных',
        'Купюры отсутствуют',
    ]

    good_values = [
        'Клавиатура работает',
        'Все карты в порядке',
        'Энергоснабжение в порядке',
        'Успешно',
        'Хорошее',
        'Полный',
        'Работает',
        'Обновления отсутствуют',
        'Ошибок не найдено',
        'Все системы работают',
        'Принтер работает'
    ]

    if row['EventType'] in incassators:
        return 'нужна инкассаторская машина'
    elif row['EventType'] in mechanic:
        return 'нужен механик'
    elif row['EventType'] in all_good:
        return 'все в порядке'
    elif row['EventType'] in chek_need:
        if pd.notna(row['Value']):
            if row['Value'] in incassator_values:
                return 'нужна инкассаторская машина'
            elif row['Value'] in good_values:
                return 'все в порядке'
            else:
                return 'нужен механик'
        else:
            return 'нужен механик'
    else:
        return 'неизвестно'

def process_csv(file_path):
    df = pd.read_csv(file_path)
    df['Label'] = df.apply(determine_label, axis=1)
    return df

def analyze_timestamps(df):
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values(by=['DeviceID', 'Timestamp'])

    atm_working_times = {}
    atm_non_working_times = {}

    for device_id, group in df.groupby('DeviceID'):
        working_times = []
        non_working_times = []
        start_time = None
        for index, row in group.iterrows():
            if row['Label'] == 'все в порядке':
                if start_time is None:
                    start_time = row['Timestamp']
            else:
                if start_time is not None:
                    working_times.append((start_time, row['Timestamp']))
                    start_time = None
                non_working_times.append((row['Timestamp'], row['Timestamp'] + pd.Timedelta(minutes=1)))
        if start_time is not None:
            working_times.append((start_time, pd.Timestamp.now()))

        atm_working_times[device_id] = working_times
        atm_non_working_times[device_id] = non_working_times

    return atm_working_times, atm_non_working_times

def get_latest_status(df):
    latest_status = {}
    for device_id, group in df.groupby('DeviceID'):
        latest_row = group.iloc[-1]
        latest_status[device_id] = latest_row['Label']
    return latest_status
