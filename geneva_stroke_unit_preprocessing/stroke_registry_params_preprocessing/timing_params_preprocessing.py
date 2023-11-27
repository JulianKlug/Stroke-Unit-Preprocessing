import pandas as pd


def preprocess_timing_params(stroke_registry_df: pd.DataFrame) -> pd.DataFrame:
    stroke_registry_df = stroke_registry_df.copy()

    stroke_registry_df['onset_datetime'] = pd.to_datetime(
        pd.to_datetime(stroke_registry_df['Onset date'], format='%Y%m%d').dt.strftime('%d-%m-%Y') \
        + ' ' + pd.to_datetime(stroke_registry_df['Onset time'], format='%H:%M',
                                                       infer_datetime_format=True).dt.strftime('%H:%M'), format='%d-%m-%Y %H:%M')

    stroke_registry_df['onset_to_admission_min'] = (pd.to_datetime(stroke_registry_df['sample_date'],
                                                                      format='%d.%m.%Y %H:%M') - pd.to_datetime(
        stroke_registry_df['onset_datetime'], format='%d-%m-%Y %H:%M:%S')).dt.total_seconds() / 60

    ## Categorize admission timings
    # Categories: 'onset_unknown', intra_hospital, '<270min', '271-540min', '541-1440min', '>1440min'

    stroke_registry_df['categorical_onset_to_admission_time'] = pd.cut(
        stroke_registry_df['onset_to_admission_min'],
        bins=[-float("inf"), 270, 540, 1440, float("inf")],
        labels=['<270min', '271-540min', '541-1440min', '>1440min'])

    stroke_registry_df['categorical_onset_to_admission_time'] = stroke_registry_df[
        'categorical_onset_to_admission_time'].cat.add_categories('intra_hospital')
    stroke_registry_df['categorical_onset_to_admission_time'] = stroke_registry_df[
        'categorical_onset_to_admission_time'].cat.add_categories('onset_unknown')

    stroke_registry_df.loc[stroke_registry_df[
                                  'Referral'] == 'In-hospital event', 'categorical_onset_to_admission_time'] = 'intra_hospital'

    stroke_registry_df.loc[stroke_registry_df[
                                  'Time of symptom onset known'] == 'no', 'categorical_onset_to_admission_time'] = 'onset_unknown'

    # add variable to account for wake-up strokes
    stroke_registry_df['wake_up_stroke'] = stroke_registry_df['Time of symptom onset known'].apply(
        lambda x: True if x == 'wake up' else False)

    timing_columns = ['categorical_onset_to_admission_time', 'wake_up_stroke']
    timing_df = stroke_registry_df[timing_columns + ['case_admission_id', 'sample_date']]

    assert timing_df.isna().sum().sum() == 0, 'Missing values in timing data.'

    timing_df = pd.melt(timing_df, id_vars=['case_admission_id', 'sample_date'], var_name='sample_label')

    ## Add column for the timing of end of acute stroke treatment
    # Extract end date for IAT
    stroke_registry_df['IAT_start_datetime'] = pd.to_datetime(
        pd.to_datetime(stroke_registry_df['Date of groin puncture'], format='%Y%m%d').dt.strftime('%d-%m-%Y') \
        + ' ' + pd.to_datetime(stroke_registry_df['Time of groin puncture'], format='%H:%M',
                               infer_datetime_format=True).dt.strftime('%H:%M'), format='%d-%m-%Y %H:%M')

    stroke_registry_df['IAT_end_datetime'] = pd.to_datetime(
        pd.to_datetime(stroke_registry_df['IAT end date'], format='%Y%m%d').dt.strftime('%d-%m-%Y') \
        + ' ' + pd.to_datetime(stroke_registry_df['IAT end time'], format='%H:%M',
                               infer_datetime_format=True).dt.strftime('%H:%M'), format='%d-%m-%Y %H:%M')

    # if restricted_stroke_registry_df['IAT_end_datetime'] is nan set it to the IAT start datetime + 2h
    stroke_registry_df.loc[stroke_registry_df['IAT_end_datetime'].isna(), 'IAT_end_datetime'] = \
    stroke_registry_df.loc[
        stroke_registry_df['IAT_end_datetime'].isna(), 'IAT_start_datetime'] + pd.Timedelta(hours=2)

    # Extract end date for IVT
    stroke_registry_df['IVT_start_datetime'] = pd.to_datetime(
        pd.to_datetime(stroke_registry_df['IVT start date'], format='%Y%m%d').dt.strftime('%d-%m-%Y') \
        + ' ' + pd.to_datetime(stroke_registry_df['IVT start time'], format='%H:%M',
                               infer_datetime_format=True).dt.strftime('%H:%M'), format='%d-%m-%Y %H:%M')

    # set ivt end datetime to ivt start datetime + 1h (duration of IVT)
    stroke_registry_df['IVT_end_datetime'] = stroke_registry_df[
                                                            'IVT_start_datetime'] + pd.Timedelta(hours=1)

    # set acute treatment end datetime to the max of ivt end datetime and iat end datetime
    stroke_registry_df['acute_treatment_end_datetime'] = stroke_registry_df[
        ['IVT_end_datetime', 'IAT_end_datetime']].max(axis=1)

    # add acute_treatment_end_datetime column to timing_df
    timing_df = timing_df.merge(stroke_registry_df[['case_admission_id', 'acute_treatment_end_datetime']],
                                on='case_admission_id', how='left')

    return timing_df
