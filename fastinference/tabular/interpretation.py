# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01_tabular.interpretation.ipynb (unless otherwise specified).

__all__ = ['base_error']

# Cell
from fastai.tabular.all import *
from scipy.cluster import hierarchy as hc
from sklearn import manifold

# Cell
def base_error(err, val):
    try: return (err-val)/err
    except ZeroDivisionError: return np.nan

# Cell
@patch
def feature_importance(x:TabularLearner, df=None, dl=None, perm_func=base_error, metric=accuracy, bs=None, reverse=True, plot=True):
    "Calculate and plot the Feature Importance based on `df`"
    x.df = df
    bs = bs if bs is not None else x.dls.bs
    if df is not None:
        dl = x.dls.test_dl(df, bs=bs)
    else:
        dl = x.dls[1]
    x_names = x.dls.x_names.filter(lambda x: '_na' not in x)
    na = x.dls.x_names.filter(lambda x: '_na' in x)
    y = x.dls.y_names
    orig_metrics = x.metrics
    x.metrics = [metric]
    try:
        results = _calc_feat_importance(x, dl, x_names, na, perm_func, reverse)
        if plot:
            _plot_importance(_ord_dic_to_df(results))
    finally: # Restore original metrics
        x.metrics = orig_metrics

    return results

# Cell
def _measure_col(learn:TabularLearner, dl:TabDataLoader, name:str, na:list):
    "Measures change after column permutation"
    col = [name]
    if f'{name}_na' in na: col.append(name)
    orig = dl.items[col].values
    perm = np.random.permutation(len(orig))
    dl.items[col] = dl.items[col].values[perm]
    with learn.no_bar(), learn.no_logging():
        metric = learn.validate(dl=dl)[1]
    dl.items[col] = orig
    return metric

# Cell
def _calc_feat_importance(learn:TabularLearner, dl:TabDataLoader, x_names:list, na:list, perm_func=base_error, reverse=True):
    "Calculates permutation importance by shuffling a column by `perm_func`"
    with learn.no_bar(), learn.no_logging():
        base_error = learn.validate(dl=dl)[1]
    importance = {}
    pbar = progress_bar(x_names)
    print("Calculating Permutation Importance")
    for col in pbar:
        importance[col] = _measure_col(learn, dl, col, na)
    for key, value in importance.items():
        importance[key] = perm_func(base_error, value)
    return OrderedDict(sorted(importance.items(), key=lambda kv: kv[1], reverse=True))

# Cell
def _ord_dic_to_df(dict:OrderedDict): return pd.DataFrame([[k,v] for k,v in dict.items()], columns=['feature','importance'])

# Cell
def _plot_importance(df:pd.DataFrame, limit=20, asc=False, **kwargs):
    "Plot importance with an optional limit to how many variables shown"
    df_copy = df.copy()
    df_copy['feature'] = df_copy['feature'].str.slice(0,25)
    df_copy = df_copy.sort_values(by='importance', ascending=asc)[:limit].sort_values(by='importance', ascending=not(asc))
    ax = df_copy.plot.barh(x='feature', y='importance', sort_columns=True, **kwargs)
    for p in ax.patches:
        ax.annotate(f'{p.get_width():.4f}', ((p.get_width() * 1.005), p.get_y()  * 1.005))

# Cell
def _cramers_corrected_stat(cm):
    "Calculates Cramers V Statistic for categorical-categorical"
    try: chi2 = scipy.stats.chi2_contingency(cm)[0]
    except: return 0.0

    if chi2 == 0: return 0.0
    n = cm.sum().sum()
    phi2 = chi2 / n
    r,k = cm.shape
    phi2corr = max(0, phi2 - ((k-1)*(r-1))/(n-1))
    rcorr = r - ((r-1)**2)/(n-1)
    kcorr = k - ((k-1)**2)/(n-1)
    return np.sqrt(phi2corr/min((kcorr-1), (rcorr-1)))

# Cell
def _get_cramer_v_matr(df:pd.DataFrame):
    "Calculate Cramers V statistic on every pair in `df`'s columns'"
    cols = list(df.columns)

    # Initialize dataframe with 1 so we won't need to fill pandas diagonal with ones :)
    corrM = pd.DataFrame(1., columns=cols, index=cols)
    for col1, col2 in progress_bar(list(itertools.combinations(cols, 2))):
        corrM.loc[col1, col2] = corrM.loc[col2, col1] = _cramers_corrected_stat(pd.crosstab(df[col1], df[col2]))

    return corrM

# Cell
@patch
def get_features_corr(x:TabularLearner, df:Optional[pd.DataFrame]=None,
                      cat_names=None, cont_names=None, cont_correlation='kendall'):
    "Return correlation matrix on `df` or train data"

    dl = x.dls.test_dl(df) if df is not None else x.dls.train
    cat_names = ifnone(cat_names, dl.cat_names)
    cont_names = ifnone(cont_names, dl.cont_names)

    # Compute correlation
    cat_corr_matrix = _get_cramer_v_matr(dl.xs[cat_names])
    cont_corr_matrix = dl.xs[cont_names].corr(method=cont_correlation)
    return cat_corr_matrix, cont_corr_matrix

# Cell
def _flatten_corr_dataframe(corr_matrix: pd.DataFrame) -> pd.Series:
    """Extract dataframe upper diagonal and flat it in a Serie"""
    corr_data = {}
    for i in range(corr_matrix.shape[0]):
        for j in range(i+1, corr_matrix.shape[1]):
            idx_name, col_name = corr_matrix.index[i], corr_matrix.index[j]
            corr_data[f"{idx_name} vs {col_name}"] = corr_matrix.iloc[i,j]
    return pd.Series(corr_data)

# Cell
@patch
@delegates(get_features_corr)
def get_top_features_corr(x:TabularLearner, df:Optional[pd.DataFrame]=None, thresh:float=0.8, **kwargs):
    "Grabs top pairs of correlation with a given correlation matrix on `df` or train data filtered by `thresh`"
    cat_corr, cont_corr = x.get_features_corr(df=df, **kwargs)

    cat_corr_flat = _flatten_corr_dataframe(cat_corr)
    cat_corr_flat = cat_corr_flat[cat_corr_flat.abs() > thresh].sort_values(ascending=False)

    cont_corr_flat = _flatten_corr_dataframe(cont_corr)
    # Get top coontinuos correlation ignoring if they are positive or negative correlated.
    abs_cont_corr = cont_corr_flat.abs()
    cont_corr_flat = cont_corr_flat[abs_cont_corr[abs_cont_corr > thresh].sort_values(ascending=False).index]

    return cat_corr_flat, cont_corr_flat

@patch
def get_top_corr_dict(x:TabularLearner, df, thresh:float=0.8):
    "Grabs top pairs of correlation with a given correlation matrix on `df` or train data filtered by `thresh`"
    warnings.warn('Deprecated method: use `get_top_features_corr`')
    cat_corr, cont_corr = x.get_top_features_corr(df, thresh)
    return {**cat_corr.to_dict(), **cont_corr.to_dict()}

# Cell
def _plot_dendrogram(corr_matrix: pd.DataFrame, leaf_font_size, ax=None):
    # Take `abs` as we don't care if correlation is positive or negative.
    corr_condensed = hc.distance.squareform(1-corr_matrix.abs().to_numpy())
    z = hc.linkage(corr_condensed, method='average')
    dendrogram = hc.dendrogram(z, labels=corr_matrix.columns, orientation='left', leaf_font_size=leaf_font_size, ax=ax)
    return dendrogram

# Cell
@patch
@delegates(get_features_corr)
def plot_dendrogram(x:TabularLearner, df: Optional[pd.DataFrame]=None,
                    figsize=None, leaf_font_size=16, **kwargs):
    "Plots dendrogram for a calculated correlation matrix. `cont_correlation` could be 'spearman' or 'kendall'"

    # Compute correlation
    cat_corr_matrix, cont_corr_matrix = x.get_features_corr(df=df, **kwargs)

    # Plot dendrogram
    if figsize is None:
        # Make plot size to fit categorical and continuous variables.
        figsize = (15, 0.02*leaf_font_size*(len(cat_corr_matrix)+len(cont_corr_matrix)+3))

    # Use constrained_layout instead of plt.tight_layout() as it's the new form.
    fig, axes = plt.subplots(2, 1, figsize=figsize, constrained_layout=True,
                             gridspec_kw={'height_ratios': [cat_corr_matrix.shape[1], cont_corr_matrix.shape[1]]})

    _plot_dendrogram(cat_corr_matrix, leaf_font_size, ax=axes[0])
    axes[0].set_title("Categorical features", fontdict={'fontsize': leaf_font_size*1.1})
    _plot_dendrogram(cont_corr_matrix.abs(), leaf_font_size, ax=axes[1])
    axes[1].set_title("Continuous features", fontdict={'fontsize': leaf_font_size*1.1})

    # plt.tight_layout()
    plt.show()
