import argparse
import json
import os
import pandas as pd
import time

from preprocessing_tools.encoding_categorical_variables.encode_categorical_variables import encode_categorical_variables
from preprocessing_tools.handling_missing_values.impute_missing_values import impute_missing_values
from preprocessing_tools.normalisation.normalisation import normalise_data
from geneva_stroke_unit_preprocessing.outcome_preprocessing.outcome_preprocessing import preprocess_outcomes
from preprocessing_tools.preprocessing_verification.outcome_presence_verification import outcome_presence_verification
from preprocessing_tools.preprocessing_verification.variable_presence_verification import variable_presence_verification
from preprocessing_tools.resample_to_time_bins.resample_to_hourly_features import resample_to_hourly_features
from geneva_stroke_unit_preprocessing.variable_assembly.variable_database_assembly import assemble_variable_database
from geneva_stroke_unit_preprocessing.variable_assembly.relative_timestamps import transform_to_relative_timestamps
from preprocessing_tools.utils import ensure_dir


def preprocess(ehr_data_path: str, stroke_registry_data_path: str,
               patient_selection_path: str,
               variable_selection_path: str,
               log_dir: str,
               winsorize: bool = True,
               start_reference: str = 'first',
               verbose: bool = True, desired_time_range: int = 72) -> pd.DataFrame:
    """
    Apply geneva_stroke_unit_preprocessing pipeline detailed in ./geneva_stroke_unit_preprocessing/readme.md
    :param ehr_data_path: path to EHR data
    :param stroke_registry_data_path: path to stroke registry (admission) data
    :param patient_selection_path: path to patient selection file
    :param variable_selection_path: path to variable selection file (should be same format as in ../variable_assembly/selected_variables_example.xlsx)
    :param log_dir: path to logging directory (this will receive logs of excluded patients and those that were not found)
    :param winsorize: whether to winsorize values outside the upper and lower bounds of 1⋅5 times the IQR are set to the upper and lower limits of the range
    :param start_reference: str, reference start time for sampling, default is 'first', other option is 'after_acute_treatment'
    - 'first': first sample date of EHR is used as reference
    - 'after_acute_treatment': if patient received IAT/IVT, treatment end is used as reference
    :param verbose:
    :param desired_time_range: number of hours to use for imputation
    :return: preprocessed feature Dataframe, preprocessed outcome dataframe
    """

    # 1. Restrict to patient selection (& filter out patients with no EHR data or EHR data with wrong dates)
    # 2. Preprocess EHR and stroke registry variables
    # 3. Restrict to variable selection
    # 4. Assemble database from lab/scales/ventilation/vitals + stroke registry subparts
    print('STARTING VARIABLE PREPROCESSING')
    feature_df = assemble_variable_database(ehr_data_path, stroke_registry_data_path,
                                            patient_selection_path, variable_selection_path,
                                            log_dir=log_dir, verbose=verbose)
    print(f'A. Number of patients: {feature_df.case_admission_id.nunique()}')

    # 5. Transform timestamps to relative timestamps from first measure
    # 6. Restrict to time range
    # - Exclude patients with data sampled in a time window < 12h
    # - Restrict to desired time range: 72h
    print('TRANSFORMING TO RELATIVE TIME AND RESTRICTING TIME RANGE')
    if start_reference == 'after_acute_treatment':
        aggregate_prior_24h = True
    else:
        aggregate_prior_24h = False

    restricted_feature_df = transform_to_relative_timestamps(feature_df, drop_old_columns=False,
                                                             restrict_to_time_range=True,
                                                             desired_time_range=desired_time_range,
                                                             enforce_min_time_range=True, min_time_range=12,
                                                             start_reference=start_reference,
                                                             aggregate_prior_24h=aggregate_prior_24h,
                                                             log_dir=log_dir)
    print(f'B. Number of patients: {restricted_feature_df.case_admission_id.nunique()}')

    # 7. Encoding categorical variables (one-hot)
    print('ENCODING CATEGORICAL VARIABLES')
    cat_encoded_restricted_feature_df = encode_categorical_variables(restricted_feature_df, verbose=verbose,
                                                                     log_dir=log_dir)
    print(f'C. Number of patients: {cat_encoded_restricted_feature_df.case_admission_id.nunique()}')

    # 8. Resampling to hourly frequency
    print('RESAMPLING TO HOURLY FREQUENCY')
    resampled_df = resample_to_hourly_features(cat_encoded_restricted_feature_df, verbose=verbose)
    print(f'D. Number of patients: {resampled_df.case_admission_id.nunique()}')

    # 9. imputation of missing values
    print('IMPUTING MISSING VALUES')
    imputed_missing_df = impute_missing_values(resampled_df, verbose=verbose, log_dir=log_dir,
                                               desired_time_range=desired_time_range)
    print(f'E. Number of patients: {imputed_missing_df.case_admission_id.nunique()}')

    # 10. normalisation
    print('APPLYING NORMALISATION')
    normalised_df = normalise_data(imputed_missing_df, winsorize=winsorize,
                                   verbose=verbose, log_dir=log_dir)
    print(f'F. Number of patients: {normalised_df.case_admission_id.nunique()}')

    # 11. geneva_stroke_unit_preprocessing outcomes
    preprocessed_outcomes = preprocess_outcomes(stroke_registry_data_path, patient_selection_path,
                                                   imputed_missing_df,
                                                   verbose=verbose)
    preprocessed_final_outcomes_df, preprocessed_continuous_outcomes_df = preprocessed_outcomes

    return normalised_df, preprocessed_final_outcomes_df, preprocessed_continuous_outcomes_df


def preprocess_and_save(ehr_data_path: str, stroke_registry_data_path: str, patient_selection_path: str,
                        variable_selection_path: str,
                        target_feature_path: str,
                        output_dir: str,
                        winsorize: bool = True,
                        start_reference: str = 'first',
                        feature_file_prefix: str = 'preprocessed_features',
                        outcome_file_prefix: str = 'preprocessed_outcomes', verbose: bool = True):
    timestamp = time.strftime("%d%m%Y_%H%M%S")
    desired_time_range = 72
    output_dir = os.path.join(output_dir, f'gsu_{os.path.basename(ehr_data_path)}_prepro_{timestamp}')
    log_dir = os.path.join(output_dir, f'logs_{timestamp}')
    saved_args = locals()
    ensure_dir(log_dir)

    # save saved_args to log_dir
    with open(os.path.join(log_dir, 'preprocessing_arguments.json'), 'w') as fp:
        json.dump(saved_args, fp)

    preprocessed_data = preprocess(ehr_data_path, stroke_registry_data_path,
                                    patient_selection_path,
                                    variable_selection_path,
                                    verbose=verbose,
                                    log_dir=log_dir,
                                    desired_time_range=desired_time_range,
                                    start_reference=start_reference)
    preprocessed_feature_df, preprocessed_final_outcome_df, preprocessed_continuous_outcomes_df = preprocessed_data
    features_save_path = os.path.join(output_dir, f'{feature_file_prefix}_{timestamp}.csv')
    final_outcomes_save_path = os.path.join(output_dir, f'{outcome_file_prefix}_final_{timestamp}.csv')
    continuous_outcomes_save_path = os.path.join(output_dir, f'{outcome_file_prefix}_continuous_{timestamp}.csv')

    preprocessed_feature_df.to_csv(features_save_path)
    preprocessed_final_outcome_df.to_csv(final_outcomes_save_path)
    preprocessed_continuous_outcomes_df.to_csv(continuous_outcomes_save_path)

    # verification of geneva_stroke_unit_preprocessing
    variable_presence_verification(preprocessed_feature_df,
                                   target_feature_path=target_feature_path,
                                   selected_variables_path=variable_selection_path,
                                   desired_time_range=desired_time_range)
    outcome_presence_verification(preprocessed_final_outcome_df, preprocessed_continuous_outcomes_df,
                                  preprocessed_feature_df, log_dir=log_dir)


if __name__ == '__main__':
    """
    Example usage:
    python preprocessing_pipeline.py -e /Users/jk1/-/-/-/Extraction20220629 -r /Users/jk1/-/-/-/post_hoc_modified/stroke_registry_post_hoc_modified.xlsx 
    -p /Users/jk1/-/-/high_frequency_data_patient_selection_with_details.csv 
    -v /Users/jk1/-/selected_variables_example.xlsx
    -o /Users/jk1/-/opsum_prepro_output
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--ehr', type=str, help='EHR data path')
    parser.add_argument('-r', '--registry', type=str, help='Registry data path')
    parser.add_argument('-p', '--patients', type=str, help='Patient selection file')
    parser.add_argument('-v', '--variable_selection', type=str, help='Variable selection file')
    parser.add_argument('-t', '--target_features', type=str,
                        help='Target feature file (target order after preprocessing)')
    parser.add_argument('-o', '--output_dir', type=str, help='Output directory')
    parser.add_argument('-w', '--winsorize', default=False, action='store_true',
                        help='Whether to winsorize values')
    parser.add_argument('-sr', '--start_reference', type=str, default='first')
    args = parser.parse_args()

    preprocess_and_save(args.ehr, args.registry,
                        args.patients, args.variable_selection,
                        args.target_features,
                        args.output_dir,
                        args.winsorize,
                        start_reference=args.start_reference)
