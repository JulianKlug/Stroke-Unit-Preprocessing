import pandas as pd
import os

final_outcomes_list = [
    'Symptomatic ICH',
    'Recurrent stroke',
    'Orolingual angioedema',
    'Death in hospital',
    'Epileptic seizure in hospital',
    'Decompr. craniectomy',
    'CEA',
    'CAS',
    'Other endovascular revascularization',
    'Other surgical revascularization',
    'PFO closure',
    'Duration of hospital stay (days)',
    '3M mRS',
    '3M NIHSS',
    '3M Stroke',
    '3M ICH',
    '3M Death',
    '3M Epileptic seizure',
    '3M delta mRS',
    '3M mRS 0-1',
    '3M mRS 0-2'
]

continuous_outcomes_list = [
    'nihss_delta_at_next_ts',
    'nihss_delta_to_best_prior_state_at_next_ts',
    'nihss_delta_to_start_state_at_next_ts'
]


def outcome_presence_verification(final_outcomes_df, continous_outcomes_df, data_df, log_dir='',
                                  final_outcomes=final_outcomes_list):
    """Verify if the outcome is present in the dataframe.

    Parameters
    ----------
    final_outcomes_df : pandas.DataFrame
        Dataframe with the outcome data.
    data_df : pandas.DataFrame
        Dataframe with the data.
    log_dir : str, optional
        Directory where the log file will be saved, by default ''
    final_outcomes : list, optional
        List of outcomes to be verified, by default outcomes_list

    Returns
    -------
    presence_df: pandas.DataFrame
    """
    n_patients = len(data_df.case_admission_id.unique())

    presence_columns = ['outcome', 'n_patients_with_outcome', 'percentage']
    presence_df = pd.DataFrame(columns=presence_columns)

    presence_df = pd.concat([presence_df, pd.DataFrame(
        {'outcome': 'overall', 'n_patients_with_outcome': n_patients, 'percentage': 100}, index=[0])],
                            ignore_index=True)

    for outcome in final_outcomes:
        # find number of case_admission_id that have an outcome
        n_patients_with_outcome = final_outcomes_df[
            (final_outcomes_df.case_admission_id.isin(data_df.case_admission_id.unique())) & (
                ~final_outcomes_df[outcome].isnull())].case_admission_id.nunique()
        presence_df = pd.concat(
            [presence_df, pd.DataFrame({'outcome': outcome, 'n_patients_with_outcome': n_patients_with_outcome,
                                        'percentage': (n_patients_with_outcome / n_patients) * 100}, index=[0])],
            ignore_index=True)

    for outcome in continuous_outcomes_list:
        # find number of case_admission_id that have an outcome
        n_patients_with_outcome = continous_outcomes_df[
            (continous_outcomes_df.case_admission_id.isin(data_df.case_admission_id.unique())) & (
                ~continous_outcomes_df[outcome].isnull())].case_admission_id.nunique()
        presence_df = pd.concat(
            [presence_df, pd.DataFrame({'outcome': outcome, 'n_patients_with_outcome': n_patients_with_outcome,
                                        'percentage': (n_patients_with_outcome / n_patients) * 100}, index=[0])],
            ignore_index=True)

    if log_dir != '':
        presence_df.to_excel(os.path.join(log_dir, 'outcome_presence.xlsx'), index=False)

    return presence_df


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--fincal_outcomes_path', type=str, required=True,
                        help='Path to the final outcomes file.')
    parser.add_argument('-c', '--continuous_outcomes_path', type=str, required=True,
                        help='Path to the continuous outcomes file.')
    parser.add_argument('-d', '--data_path', type=str, required=True, help='Path to the data file.')
    parser.add_argument('-l', '--log_dir', type=str, default='', help='Directory where the log file will be saved.')
    args = parser.parse_args()

    final_outcomes_df = pd.read_csv(args.outcomes_path)
    cont_outcomes_df = pd.read_csv(args.continuous_outcomes_path)
    data_df = pd.read_csv(args.data_path)

    outcome_presence_verification(final_outcomes_df, cont_outcomes_df, data_df, args.log_dir)
