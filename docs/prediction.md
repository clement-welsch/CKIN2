# Experimental prediction (#27)

Open notebook/prediction_book.ipynb. It shares the fixed-cohort market index from
the global notebook and forecasts next month's index, globally and per category.
It does not forecast portfolio cash flows, quantities or realized gains. There
are no trading signals and no invented confidence intervals.

The current calendar month is excluded. At each completed month-end, the latest
index known by the close of that day is selected with a 45-day maximum price
age. Labels are month-end dates meaning end-of-day information. Acquisition
references and observations with estimated dates are excluded before sampling.
Missing months stay missing; features never interpolate or bridge gaps.

Persistence forecasts the latest level. Trend extrapolates the last monthly
change. Ridge uses level, previous change and three-month mean. Each origin
gets a fresh StandardScaler/Ridge pipeline trained only on pairs whose target
month is already observed. Alpha=1, SVD, random_state=0, min_train=12 valid pairs;
there is no random holdout or hyperparameter search. Forecasts are clipped at
zero. Twelve pairs is an engineering starting threshold, not evidence of
statistical reliability. A larger independent evaluation history is needed.

MAE and RMSE are in index points and remain defined at zero. baseline_common
compares baselines on the same dates; model_common compares all three methods
only on model-eligible dates. Window counts, date ranges, training counts and
last available training-target dates are included. Sparse data produces a clear
audit and available baselines, with Ridge unavailable. Future forecasts require
the latest grid month and its predecessor to be valid, so stale trailing months
cannot silently generate a forecast labelled as current.

The cohort is the currently tracked inventory, introducing retrospective
selection bias. This is a forecasting experiment, not a historical simulation
of an investable strategy. Better historical membership, volume and executed
prices could support later experiments; none are fabricated in this version.

Tests perturb future targets to check that earlier forecasts are unchanged,
verify training-target cutoffs, common metric dates, gaps, zeros and estimated
dates, and execute the notebook on long, short and empty synthetic histories.
All generated figures serialize and all CSV bytes are unchanged. Browser pixel
rendering and forecasting accuracy on private data are not validated.

Methodology references:
- https://scikit-learn.org/stable/common_pitfalls.html
- https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html
