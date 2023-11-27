import pandas as pd
import numpy as np

from geneva_stroke_unit_preprocessing.patient_selection.restrict_to_patient_selection import \
    restrict_to_patient_selection
from geneva_stroke_unit_preprocessing.utils import create_registry_case_identification_column

outcome_columns = ["Symptomatic ICH",
                   "Symptomatic ICH date",
                   "Recurrent stroke",
                   "Recurrent stroke date",
                   "Orolingual angioedema",
                   "Death in hospital",
                   "Death at hospital date",
                   "Death at hospital time",
                   "Death at hospital cause",
                   "Epileptic seizure in hospital",
                   "Epileptic seizure in hospital date",
                   "Decompr. craniectomy",
                   "Decompr. craniectomy date",
                   "CEA",
                   "CEA date",
                   "CAS",
                   "CAS date",
                   "Other endovascular revascularization",
                   "Other surgical revascularization",
                   "Other surgical revascularization date",
                   "Other surgical revascularization spec",
                   "PFO closure",
                   "PFO closure date",
                   "Discharge destination",
                   "Discharge date",
                   "Discharge time",
                   "Duration of hospital stay (days)",
                   "3M date",
                   "3M mode",
                   "3M mRS",
                   "3M NIHSS", "3M Stroke",
                   "3M Stroke date",
                   "3M ICH", '3M ICH date', '3M Death', '3M Death date', '3M Death cause',
                   '3M Epileptic seizure', '3M Epileptic seizure date', '3M delta mRS']


def preprocess_outcomes(stroke_registry_data_path: str, patient_selection_path: str,
                        non_normalised_feature_df: pd.DataFrame,
                        verbose: bool = True):
    """
    Preprocesses outcomes:
    - final outcomes (at 3 months): mrs, death
    - continuous outcomes (at every time step): early neurological deterioration
    :param stroke_registry_data_path:
    :param patient_selection_path:
    :param non_normalised_feature_df: preprocessed feature dataframe (but not normalised), e.g.: imputed_missing_df
    :param verbose:
    :return:
    """


    # Preprocess final outcomes
    stroke_registry_df = pd.read_excel(stroke_registry_data_path)

    stroke_registry_df['patient_id'] = stroke_registry_df['Case ID'].apply(lambda x: x[8:-4])
    stroke_registry_df['EDS_last_4_digits'] = stroke_registry_df['Case ID'].apply(lambda x: x[-4:])

    stroke_registry_df['case_admission_id'] = create_registry_case_identification_column(stroke_registry_df)
    restricted_stroke_registry_df = restrict_to_patient_selection(stroke_registry_df, patient_selection_path,
                                                                  restrict_to_event_period=False,
                                                                  verbose=verbose)

    # if death in hospital, set mRs to 6
    restricted_stroke_registry_df.loc[restricted_stroke_registry_df['Death in hospital'] == 'yes', '3M mRS'] = 6
    # if 3M Death and 3M mRS nan, set mrs to 6
    restricted_stroke_registry_df.loc[(restricted_stroke_registry_df['3M Death'] == 'yes') &
                                      (restricted_stroke_registry_df['3M mRS'].isna()), '3M mRS'] = 6

    restricted_stroke_registry_df['3M delta mRS'] = restricted_stroke_registry_df['3M mRS'] - \
                                                    restricted_stroke_registry_df[
                                                        'Prestroke disability (Rankin)']

    # if death in hospital set 3M Death to yes
    restricted_stroke_registry_df.loc[restricted_stroke_registry_df['Death in hospital'] == 'yes', '3M Death'] = 'yes'
    # if 3M mRs == 6, set 3M Death to yes
    restricted_stroke_registry_df.loc[restricted_stroke_registry_df['3M mRS'] == 6, '3M Death'] = 'yes'
    # if 3M mRs not nan and not 6, set 3M Death to no
    restricted_stroke_registry_df.loc[(restricted_stroke_registry_df['3M mRS'] != 6) &
                                      (~restricted_stroke_registry_df['3M mRS'].isna())
                                      & (restricted_stroke_registry_df['3M Death'].isna()), '3M Death'] = 'no'

    final_outcome_df = restricted_stroke_registry_df[["case_admission_id"] + outcome_columns]

    # restrict to plausible ranges
    final_outcome_df.loc[final_outcome_df['3M delta mRS'] < 0, '3M delta mRS'] = 0
    final_outcome_df.loc[final_outcome_df['Duration of hospital stay (days)'] > 365, 'Duration of hospital stay (days)'] = np.nan

    # add binarised outcomes if 3M mRS is not nan
    final_outcome_df['3M mRS 0-1'] = np.where(final_outcome_df['3M mRS'].isna(), np.nan, np.where(final_outcome_df['3M mRS'] <= 1, 1, 0))
    final_outcome_df['3M mRS 0-2'] = np.where(final_outcome_df['3M mRS'].isna(), np.nan, np.where(final_outcome_df['3M mRS'] <= 2, 1, 0))

    # binarise 3M Death and Death in hospital
    final_outcome_df.loc[final_outcome_df['3M Death'] == 'yes', '3M Death'] = 1
    final_outcome_df.loc[final_outcome_df['3M Death'] == 'no', '3M Death'] = 0
    final_outcome_df.loc[final_outcome_df['Death in hospital'] == 'yes', 'Death in hospital'] = 1
    final_outcome_df.loc[final_outcome_df['Death in hospital'] == 'no', 'Death in hospital'] = 0

    assert final_outcome_df['3M mRS 0-2'].value_counts().sum() == final_outcome_df[
        '3M mRS'].value_counts().sum(), "Number of 3M mRS 0-2 not equal to 3M mRS"
    assert final_outcome_df['3M mRS 0-1'].value_counts().sum() == final_outcome_df[
        '3M mRS'].value_counts().sum(), "Number of 3M mRS 0-1 not equal to 3M mRS"


    # Preprocess continuous outcomes
    # Early neurological deterioration
    end_df = non_normalised_feature_df[(non_normalised_feature_df.sample_label == 'median_NIHSS')]

    # verify that relative_sample_date_hourly_cat is sorted
    assert end_df.groupby('case_admission_id')['relative_sample_date_hourly_cat'].is_monotonic_increasing.all()

    # First derivative of median_NIHSS
    # (for every case_admission_id / timebin combination, substract previous value from current value)
    end_df['nihss_delta'] = end_df.groupby(['case_admission_id'])['value'].diff()
    end_df['nihss_delta'] = end_df['nihss_delta'].fillna(0)

    # Delta to best prior state and delta to start state
    end_df['best_prior_state'] = end_df.groupby(['case_admission_id'])['value'].cummin()
    end_df['nihss_delta_to_best_prior_state'] = end_df['value'] - end_df['best_prior_state']
    end_df['start_state'] = end_df.groupby(['case_admission_id'])['value'].transform('first')
    end_df['nihss_delta_to_start_state'] = end_df['value'] - end_df['start_state']

    # Delta at next time step
    end_df['nihss_delta_at_next_ts'] = end_df.groupby(['case_admission_id'])['nihss_delta'].shift(-1)
    end_df['nihss_delta_to_best_prior_state_at_next_ts'] = end_df.groupby(['case_admission_id'])['nihss_delta_to_best_prior_state'].shift(-1)
    end_df['nihss_delta_to_start_state_at_next_ts'] = end_df.groupby(['case_admission_id'])['nihss_delta_to_start_state'].shift(-1)

    end_df.drop(columns=['sample_label', 'impute_missing_as', 'best_prior_state', 'start_state'], inplace=True)
    end_df.rename(columns={'value': 'nihss'}, inplace=True)

    return final_outcome_df, end_df
