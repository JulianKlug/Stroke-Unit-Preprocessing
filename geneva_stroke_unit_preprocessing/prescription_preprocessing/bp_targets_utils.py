import re


def target_variable_identification_scheme(condition):
    start_regex = '(?:^| |>|&GT|\(|,)'
    end_regex = '(?= |$|>|<|&GT|&LT|&NBSP|\)|1|,)'
    if condition is None:
        return None

    # if ' TAM' followed by a space or a > or a < or the end of the string
    TAM_equivalents = ['TAM', 'TENSION ARTÉRIELLE MOYENNE', 'PAM', 'TAMOYENNE', 'TENSION MOYENNE', 'TASM', 'TSAM', 'TA M']
    TAM_rgx = rf'{start_regex}({"|".join(TAM_equivalents)}){end_regex}'
    if re.search(TAM_rgx, condition) is not None:
        return 'TAM'

    # if a number in this format XXX/XX or XXX/XXX is given, return 'TA'
    if re.search(r'\d{2,3}/\d{2,3}', condition) is not None:
        return 'TA'

    TAS_equivalents = ['TAS', 'TENSION ARTÉRIELLE SYSTOLIQUE', 'PAS', 'TASYS', 'SISOTLIQUE', 'TENSION SYSTOLIQUE',
                       'TASYSTOLIQUE', 'SYSTOLIQUE', 'HTAS', 'SYSTOLE', 'SISTOLIQUE', 'SISTOLE', 'SYSTOLES']
    TAS_rgx = rf'{start_regex}({"|".join(TAS_equivalents)}){end_regex}'
    if re.search(TAS_rgx, condition) is not None:
        return 'TAS'

    # if only one value provided for target, use as TAS (two variable target interpreted as TA above)
    TA_equivalents = ['TA', 'PA']
    TAS_rgx = rf'{start_regex}({"|".join(TA_equivalents)}){end_regex}'
    if re.search(TAS_rgx, condition) is not None:
        return 'TAS'

    # if there is a single 2 or 3 digit number, if number > 110, return 'TAS', else return 'TAM'
    target_pressure_matches = re.findall(r'\d{2,3}', condition)
    if len(target_pressure_matches) > 0:
        # take the first number found (because no better rule yet)
        if int(target_pressure_matches[0]) > 110:
            return 'TAS'
        else:
            return 'TAM'

    else:
        return "unknown"



def target_value_identification_scheme(condition, mmHg_equivalents_upper):
    if condition is None:
        return None

    # patch common mistypings
    condition = condition.replace('1600', '160')
    condition = condition.replace('2201', '220')
    condition = condition.replace('1140', '140')
    condition = condition.replace('995', '95')
    condition = condition.replace('22O', '220')

    # if there is a pattern such as XXX/XXX [mmHg equivalent] or XXX/XX [mmHg equivalent] (with or without spaces)
    # return the two numbers
    mmHg_equivalents_rgx = "|".join(mmHg_equivalents_upper)
    target_pressure_matches = re.search(rf'(\d{{2,3}})/(\d{{2,3}})( |)({mmHg_equivalents_rgx})', condition)
    if target_pressure_matches is not None:
        target_pressure_string = re.search(r'(\d{2,3})/(\d{2,3})', target_pressure_matches[0])
        if target_pressure_string is not None:
            return target_pressure_string[0]

    # check for XXX/XXX or XXX/XX pattern
    target_pressure_matches = re.findall(r'(\d{2,4})/(\d{2,3})', condition)
    if len(target_pressure_matches) > 0:
        value1 = target_pressure_matches[0][0]
        value2 = target_pressure_matches[0][1]

        # if the first number has 4 digits, divide by 10
        if len(value1) == 4:
            return f'{int(value1)[:-1]}/{value2}'

        # if the second number > first number, swap
        if int(value2) > int(value1):
            temp_first = value1
            value1 = value2
            value2 = temp_first

        # to safeguard against other numbers presenting as XX/XX, TAS should be > 75
        if int(value1) > 75:
            return f'{value1}/{value2}'

    # if there is a single 2 or 3 digit number, with a leading > or <, return the number (without space in between)
    target_pressure_matches = re.findall(
        r'(<|<, OU =|INFÉRIEURE À|>|&GT|&LT|SUPERIEUR A|SUPÉRIEURE À|SUPÉRIEUR À|SUP À|SUP&NBSP, À| PLUS DE|>, OU =|PLUS QUE)(,|)(| |,)(| |,)(\d{2,3})',
        condition)
    # filter > pertaining to B> or I>
    target_pressure_matches = [m for m in target_pressure_matches
                               if not (m[0] == '>' and
                                       (condition.split(''.join(m))[0][-1] == 'I'
                                        or condition.split(''.join(m))[0][-1] == 'B'))]
    if len(target_pressure_matches) > 0:
        # take the first number found (because no better rule yet)
        if int(target_pressure_matches[0][-1]) >= 50:
            return target_pressure_matches[0][-1]

    # identify a range
    target_ranges_matches = re.search(
        rf'(\d{{2,3}})( |)({mmHg_equivalents_rgx}|)(| )(-|ET|ET <,|ET &LT,|AU MAXIUMUM<BR>AU MIN)(| )(\d{{2,3}})( |)({mmHg_equivalents_rgx}|)',
        condition)
    if target_ranges_matches is not None:
        target_range_string1 = re.search(r'(\d{2,3})-(\d{2,3})', target_ranges_matches[0])
        if target_range_string1 is not None:
            return target_range_string1[0]
        target_range_string2 = re.findall(r'(\d{2,3})', target_ranges_matches[0])
        if len(target_range_string2) > 0:
            if (int(target_range_string2[1]) > int(target_range_string2[0])) \
                    and (int(target_range_string2[1]) > 65):
                return f'{target_range_string2[0]}-{target_range_string2[1]}'
            elif int(target_range_string2[0]) > 65:
                return f'{target_range_string2[1]}-{target_range_string2[0]}'

    # if there is a single 2 or 3 digit number
    target_pressure_matches = re.findall(r'\d{2,3}', condition)
    if len(target_pressure_matches) > 0:
        # take the first number found (because no better rule yet)

        # excluded instances where match is followed by 'MG'
        rest_condition = condition.split(target_pressure_matches[0])[-1]
        if rest_condition.startswith('MG') or rest_condition.startswith(' MG'):
            return "unknown"

        if int(target_pressure_matches[0]) > 50:
            return target_pressure_matches[0]

    return "unknown"


def target_condition_identification_scheme(condition, mmHg_equivalents_upper):
    if condition is None:
        return None

    # identify a range
    mmHg_equivalents_rgx = "|".join(mmHg_equivalents_upper)
    target_ranges_matches = re.search(
        rf'(\d{{2,3}})( |)({mmHg_equivalents_rgx}|)(| )(-|ET|ET <,|ET &LT,|AU MAXIUMUM<BR>AU MIN)(| )(\d{{2,3}})( |)({mmHg_equivalents_rgx}|)',
        condition)
    if target_ranges_matches is not None:
        return 'range'

    # if there is a single 2 or 3 digit number, with a leading  < (or equivalent), return <
    inferior_than_equivalents = ['<', '<, OU =', 'INFÉRIEURE À', '&LT', '&LT, OU = À']
    inferior_than_equivalents_rgx = '|'.join(inferior_than_equivalents)
    inferior_than_matches = re.findall(rf'({inferior_than_equivalents_rgx})(,|)(| |,)(| |,)(\d{{2,3}})', condition)
    if len(inferior_than_matches) > 0:
        if int(inferior_than_matches[0][-1]) >= 50:
            return '<'

    # if there is a single 2-3 digit number, with a leading >, return >
    superior_than_equivalents = ['>', '&GT', 'SUPERIEUR A', 'SUPÉRIEURE À', 'SUPÉRIEUR À', 'SUP À', 'SUP&NBSP, À',
                                 ' PLUS DE', '>, OU =', 'PLUS QUE', 'AU DESSUS', 'AU-DESSUS', 'SUPÉRIEURE AUX',
                                 'SUPERIEUR À']
    superior_than_equivalents_rgx = '|'.join(superior_than_equivalents)
    superior_than_matches = re.findall(rf'({superior_than_equivalents_rgx})(,|)(| |,)(| |,)(\d{{2,3}})', condition)
    superior_than_matches = [m for m in superior_than_matches
                             if not (m[0] == '>' and
                                     (condition.split(''.join(m))[0][-1] == 'I'
                                      or condition.split(''.join(m))[0][-1] == 'B'))]
    if len(superior_than_matches) > 0:
        if int(superior_than_matches[0][-1]) >= 50:
            return '>'

    # identify isolated < or >
    # remove isolated <I>, </I>, <B>, </B>, as well as I> and B>
    to_replace = ['<I>', '</I>', '<B>', '</B>', 'I>', 'B>']
    for r in to_replace:
        condition = condition.replace(r, '')

    any_inferior_than_matches = re.findall(rf'({inferior_than_equivalents_rgx})', condition)
    if len(any_inferior_than_matches) > 0:
        return '<'

    any_superior_than_matches = re.findall(rf'({superior_than_equivalents_rgx}|MAX|EN RÉSERVE SI)', condition)
    if len(any_superior_than_matches) > 0:
        return '>'

    return "unknown"


def ensure_correct_order_for_range(x):
    # check if '-' in x
    if not '-' in x:
        return x

    # check if first number is smaller than second number
    numbers = x.split('-')
    if int(numbers[0]) < int(numbers[1]):
        return x
    else:
        return f'{numbers[1]}-{numbers[0]}'


def ensure_correct_order_for_sbp_dbp(x):
    # check if '/' in x
    if not '/' in x:
        return x

    # check if first number is greater than second number
    numbers = x.split('/')
    if int(numbers[0]) > int(numbers[1]):
        return x
    else:
        return f'{numbers[1]}/{numbers[0]}'