# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00a_inference.text.ipynb (unless otherwise specified).

__all__ = []

# Cell
from fastai2.text.all import *
from .inference import _fully_decode, _decode_loss
import matplotlib.cm as cm
import html
from IPython.display import display, HTML

# Cell
@patch
def get_preds(x:LMLearner, ds_idx=1, dl=None, raw_outs=False, decoded_loss=True, fully_decoded=False, concat_dim=0,
             **kwargs):
    "Get predictions with possible decoding"
    inps, outs, dec_out, raw = [], [], [], []
    if dl is None: dl = x.dls[ds_idx].new(shuffle=False, drop_last=False)
    x.model.eval()
    for batch in dl:
        with torch.no_grad():
            inps.append(batch[:x.dls.n_inp])
            if decoded_loss or fully_decoded:
                out = x.model(*batch[:x.dls.n_inp])[0]
                raw.append(out)
                dec_out.append(x.loss_func.decodes(out))
            else:
                raw.append(x.model(*batch[:x.dls.n_inp])[0])
    raw = torch.cat(raw, dim=concat_dim).cpu().numpy()
    if decoded_loss or fully_decoded:
        dec_out = torch.cat(dec_out, dim=0)
    if not raw_outs:
        try: outs.insert(0, x.loss_func.activation(tensor(raw)).numpy())
        except: outs.insert(0, dec_out)
    else:
        outs.insert(0, raw)
    if fully_decoded: outs = _fully_decode(x.dls, inps, outs, dec_out, False)
    if decoded_loss: outs = _decode_loss(x.dls.categorize.vocab, dec_out, outs)
    return outs

# Cell
@patch
def get_preds(x:TextLearner, ds_idx=1, dl=None, raw_outs=False, decoded_loss=True, fully_decoded=False,
             **kwargs):
    "Get predictions with possible decoding"
    inps, outs, dec_out, raw = [], [], [], []
    if dl is None: dl = x.dls[ds_idx].new(shuffle=False, drop_last=False)
    x.model.eval()
    for batch in dl:
        with torch.no_grad():
            inps.append(batch[:x.dls.n_inp])
            if decoded_loss or fully_decoded:
                out = x.model(*batch[:x.dls.n_inp])[0]
                raw.append(out)
                dec_out.append(x.loss_func.decodes(out))
            else:
                raw.append(x.model(*batch[:x.dls.n_inp])[0])
    raw = torch.cat(raw, dim=0).cpu().numpy()
    if decoded_loss or fully_decoded:
        dec_out = torch.cat(dec_out, dim=0)
    if not raw_outs:
        try: outs.insert(0, x.loss_func.activation(tensor(raw)).numpy())
        except: outs.insert(0, dec_out)
    else:
        outs.insert(0, raw)
    if fully_decoded: outs = _fully_decode(x.dls, inps, outs, dec_out, False)
    if decoded_loss: outs = _decode_loss(x.dls.categorize.vocab, dec_out, outs)
    return outs

# Cell
@patch
def predict(x:LMLearner, text, n_words=1, no_unk=True, temperature=1., min_p=None,
                decoder=decode_spec_tokens, only_last_word=False):
        "Predict `n_words` from `text`"
        x.model.reset()
        idxs = idxs_all = x.dls.test_dl([text]).items[0].to(x.dls.device)
        unk_idx = x.dls.vocab.index(UNK)
        for _ in (range(n_words)):
            preds = x.get_preds(dl=[(idxs[None],)], decoded_loss=False)
            res = preds[0][0][-1]
            if no_unk: res[unk_idx] = 0.
            if min_p is not None:
                if (res >= min_p).float().sum() == 0:
                    warn(f"There is no item with probability >= {min_p}, try a lower value.")
                else: res[res < min_p] = 0.
            if temperature != 1.: res.pow_(1 / temperature)
            res = tensor(res)
            idx = torch.multinomial(res, 1).item()
            idxs = idxs_all = torch.cat([idxs_all, idxs.new([idx])])
            if only_last_word: idxs = idxs[-1][None]
        decoder=decode_spec_tokens
        num = x.dls.train_ds.numericalize
        tokens = [num.vocab[i] for i in idxs_all if num.vocab[i] not in [BOS, PAD]]
        sep = x.dls.train_ds.tokenizer[-1].sep
        return sep.join(decoder(tokens))

# Cell
def _value2rgba(x, cmap=cm.RdYlGn, alpha_mult=1.0):
    "Convert a value `x` from 0 to 1 (inclusive) to an RGBA tuple according to `cmap` times transparency `alpha_mult`."
    c = cmap(x)
    rgb = (np.array(c[:-1]) * 255).astype(int)
    a = c[-1] * alpha_mult
    return tuple(rgb.tolist() + [a])

# Cell
def _eval_dropouts(mod):
        module_name =  mod.__class__.__name__
        if 'Dropout' in module_name or 'BatchNorm' in module_name: mod.training = False
        for module in mod.children(): _eval_dropouts(module)

# Cell
def _piece_attn_html(pieces, attns, sep=' ', **kwargs):
    html_code,spans = ['<span style="font-family: monospace;">'], []
    for p, a in zip(pieces, attns):
        p = html.escape(p)
        c = str(_value2rgba(a, alpha_mult=0.5, **kwargs))
        spans.append(f'<span title="{a:.3f}" style="background-color: rgba{c};">{p}</span>')
    html_code.append(sep.join(spans))
    html_code.append('</span>')
    return ''.join(html_code)

def _show_piece_attn(*args, **kwargs):
    from IPython.display import display, HTML
    display(HTML(_piece_attn_html(*args, **kwargs)))

# Cell
def _intrinsic_attention(learn, text, class_id=None):
    "Calculate the intrinsic attention of the input w.r.t to an output `class_id`, or the classification given by the model if `None`."
    learn.model.train()
    _eval_dropouts(learn.model)
    learn.model.zero_grad()
    learn.model.reset()
    dl = learn.dls.test_dl([text])
    batch = next(iter(dl))[0]
    emb = learn.model[0].module.encoder(batch).detach().requires_grad_(True)
    lstm = learn.model[0].module(emb, True)
    learn.model.eval()
    cl = learn.model[1]((lstm, torch.zeros_like(batch).bool(),))[0].softmax(dim=-1)
    if class_id is None: class_id = cl.argmax()
    cl[0][class_id].backward()
    attn = emb.squeeze().abs().sum(dim=-1)
    attn /= attn.max()
    tok, _ = learn.dls.decode_batch((*tuplify(batch), *tuplify(cl)))[0]
    return tok, attn

# Cell
@patch
def intrinsic_attention(x:TextLearner, text:str, class_id:int=None, **kwargs):
    "Shows the `intrinsic attention for `text`, optional `class_id`"
    if isinstance(x, LMLearner): raise Exception("Language models are not supported")
    text, attn = _intrinsic_attention(x, text, class_id)
    return _show_piece_attn(text.split(), to_np(attn), **kwargs)