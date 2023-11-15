import pandas as pd
import os

from geneva_stroke_unit_preprocessing.prescription_preprocessing.bp_targets_utils import \
    target_variable_identification_scheme, target_value_identification_scheme, target_condition_identification_scheme, \
    ensure_correct_order_for_range, ensure_correct_order_for_sbp_dbp
from geneva_stroke_unit_preprocessing.prescription_preprocessing.prescription_utils import remove_pharma_drug_name, \
    count_dates_occurrences, get_prescription_end_date, create_intervals
from geneva_stroke_unit_preprocessing.utils import create_ehr_case_identification_column, \
    find_element_with_string_in_list


def extract_anti_hypertensive_strategy(prescription_df, interval=60, verbose=False):
    prescription_df['case_admission_id'] = create_ehr_case_identification_column(prescription_df)

    columns_to_drop = ['nr', 'patient_id', 'eds_end_4digit', 'eds_manual', 'DOB', 'begin_date',
                       'end_date', 'death_date', 'death_hosp', 'eds_final_id',
                       'eds_final_begin', 'eds_final_end', 'eds_final_patient_id',
                       'eds_final_birth', 'eds_final_death', 'eds_final_birth_str',
                       'date_from', 'date_to']
    prescription_df.drop(columns_to_drop, axis=1, inplace=True)

    ## 1. identify prescriptions related to BP strategies
    # - find BP goal identifiers in long_name

    mmHg_equivalents = ['mmHg', 'mm Hg', 'mmg Hg', 'mmhHg', 'mHg']
    mmHg_equivalents_upper = [s.upper() for s in mmHg_equivalents]

    bp_goal_identifiers = [' TAM ', ' TAS ', ' TA '] + mmHg_equivalents
    bp_goal_identifiers_upper = [s.upper() for s in bp_goal_identifiers]

    long_name_parts = prescription_df[(prescription_df.long_name.str.upper().str.contains(
        '|'.join(bp_goal_identifiers).upper()) == True)].long_name.str.upper().str.split('<B>')

    bp_prescriptions_name_and_date_df = prescription_df[
        (prescription_df.long_name.str.upper().str.contains('|'.join(bp_goal_identifiers).upper()) == True)][
        ['case_admission_id', 'short_name', 'start_date', 'end_date.1', 'stop_date']]

    # select the long_name_parts containing a string containg bp_goal_identifiers (upper case)
    conditions = long_name_parts.apply(lambda x: find_element_with_string_in_list(x, bp_goal_identifiers_upper))

    ## 2. identify targeted variable: TAM / TAS / TA (TAS/TAD)
    target_variables = conditions.apply(lambda x: target_variable_identification_scheme(x))

    ## 3. identify targeted value: X mmHg
    target_values = conditions.apply(lambda x: target_value_identification_scheme(x, mmHg_equivalents_upper))

    ## 4. identify condition: > / < / range (-)
    target_conditions = conditions.apply(lambda x: target_condition_identification_scheme(x, mmHg_equivalents_upper))

    # join all the information in a single dataframe
    bp_targets_df = bp_prescriptions_name_and_date_df.join(
        pd.DataFrame([conditions, target_variables, target_conditions, target_values]).T)
    bp_targets_df.columns = ['case_admission_id', 'short_name', 'start_date', 'end_date', 'stop_date', 'condition',
                             'target_variable', 'target_condition', 'target_value']

    ## Filter out unwanted prescriptions
    # - remove nimodipine, isosorbide dinitrate, sacubitril + valsartan, altéplase, sacubitril + valsartan Entresto cp, insuline aspart, midazolam, clopidogrel
    # - si contiens cp, only keep first word
    # - filter out if long_name contains "NE PAS DONNER"
    # - filter out if condition contains multiple dates

    bp_targets_df = bp_targets_df[~bp_targets_df.short_name.isin(
        ['nimodipine', 'isosorbide dinitrate', 'sacubitril + valsartan', 'altéplase',
         'sacubitril + valsartan Entresto cp', 'insuline aspart', 'midazolam', 'clopidogrel'])]
    bp_targets_df = bp_targets_df[~bp_targets_df.condition.str.contains('NE PAS DONNER')]

    bp_targets_df.short_name = bp_targets_df.short_name.apply(lambda x: remove_pharma_drug_name(x))
    # enforce correct order for range and sbp/dbp
    bp_targets_df.target_value = bp_targets_df.target_value.apply(lambda x: ensure_correct_order_for_range(x))
    bp_targets_df.target_value = bp_targets_df.target_value.apply(lambda x: ensure_correct_order_for_sbp_dbp(x))
    # filter out prescription with multiple dates in condition
    bp_targets_df = bp_targets_df[
        ~bp_targets_df.filter(like='condition', axis=1).apply(count_dates_occurrences, axis=1)]

    ## Seperate anti-hypertensive drugs from vasopressors/fluids
    path_to_current_file_directory = os.path.dirname(os.path.realpath(__file__))
    drug_class_lists_df = pd.read_excel(os.path.join(path_to_current_file_directory, 'drug_class_short_names.xlsx'))
    antihypertensives_bp_targets_df = bp_targets_df[bp_targets_df.short_name.isin(drug_class_lists_df.antihypertensive)]

    ##### Strategy labels:
    # - 0: MAP < 105 mmHg
    # - 1: SBP < 140 mmHg
    # - 2: SBP < 150 mmHg
    # - 3: SBP < 160 mmHg
    # - 4: MAP < 130 mmHg
    # - 5: SBP < 180 mmHg
    # - 6: SBP < 220 mmHg
    # - 7: not limited
    antihypertensives_bp_targets_df['target_strategy'] = antihypertensives_bp_targets_df.apply(
        target_strategy_identification, axis=1)

    antihypertensives_bp_targets_df = antihypertensives_bp_targets_df[
        antihypertensives_bp_targets_df.target_strategy.notnull()]

    antihypertensives_bp_targets_df = antihypertensives_bp_targets_df.drop_duplicates()

    #### Format time (to 1 entry per time resolution interval)
    datetime_format = '%d.%m.%Y %H:%M'

    def get_prescription_intervals(x, interval):
        prescription_end_date = get_prescription_end_date(x.end_date, x.stop_date, datetime_format)
        return create_intervals(x.start_date, prescription_end_date, interval, datetime_format)

    with_intervals_df = antihypertensives_bp_targets_df.apply(lambda x: get_prescription_intervals(x, interval), axis=1)
    final_antihypertensive_strategy_df = antihypertensives_bp_targets_df.join(with_intervals_df)
    final_antihypertensive_strategy_df = final_antihypertensive_strategy_df.melt(id_vars=antihypertensives_bp_targets_df.columns, value_name='sample_date')
    final_antihypertensive_strategy_df.drop(columns=['variable'], inplace=True)
    # drop NaT in sample_date
    final_antihypertensive_strategy_df.dropna(subset=['sample_date'], inplace=True)

    # set flag to impute missing as 7
    final_antihypertensive_strategy_df['impute_missing_as'] = 7

    return final_antihypertensive_strategy_df


def target_strategy_identification(x):
    ##### Strategy labels:
    # - 0: MAP < 105 mmHg
    # - 1: SBP < 140 mmHg
    # - 2: SBP < 150 mmHg
    # - 3: SBP < 160 mmHg
    # - 4: MAP < 130 mmHg
    # - 5: SBP < 180 mmHg
    # - 6: SBP < 220 mmHg
    # - 7: not limited
    # strategy 0: MAP < 105 mmHg
    if any([
        (x.target_variable == 'TAM') & (x.target_value == '105'),
        ('-' in x.target_value) & (x.target_value.endswith('105'))
    ]):
        return 0

    # strategy 1: SBP < 140 mmHg
    if any([
        (x.target_variable != 'TAM') & (x.target_value == '140'),
        (x.target_variable != 'TAM') & ('-' in x.target_value) & (x.target_value.endswith('140')),
        ('140/' in x.target_value)
    ]):
        return 1

    # strategy 2: SBP < 150 mmHg
    if any([
        (x.target_variable != 'TAM') & (x.target_value == '150'),
        (x.target_variable != 'TAM') & ('-' in x.target_value) & (x.target_value.endswith('150')),
        ('150/' in x.target_value)
    ]):
        return 2

    # strategy 3: SBP < 160 mmHg
    if any([
        (x.target_variable != 'TAM') & (x.target_value == '160'),
        (x.target_variable != 'TAM') & ('-' in x.target_value) & (x.target_value.endswith('160')),
        ('160/' in x.target_value)
    ]):
        return 3

    # strategy 4: MAP < 130 mmHg
    if any([
        (x.target_variable == 'TAM') & (x.target_value == '130'),
        (x.target_variable == 'TAM') & ('-' in x.target_value) & (x.target_value.endswith('130'))
    ]):
        return 4

    # strategy 5: SBP < 180 mmHg
    if any([
        (x.target_value == '180'),
        (x.target_variable != 'TAM') & ('-' in x.target_value) & (x.target_value.endswith('180')),
        ('180/' in x.target_value)
    ]):
        return 5

    # strategy 6: SBP < 220 mmHg

    if any([
        (x.target_value == '220'),
        (x.target_variable != 'TAM') & ('-' in x.target_value) & (x.target_value.endswith('220')),
        ('220/' in x.target_value)
    ]):
        return 6

    return None
