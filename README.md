# Training Register

Record trainings, measure what people learned, and issue certificates that anyone can check. It runs offline.

```
python -m training_register
```

Then open http://127.0.0.1:8038. It needs Python 3.10 or newer.

## What it does

- **Courses and participants:** attendance, and scores before and after
- **Learning gain:** the change in score, and Hake's normalised gain, which is the share of possible improvement achieved, with a paired t-test and effect size
- **Clear completion rules:** attendance and a pass mark decide who earns a certificate, and each person sees why
- **Reach:** participants by sex and age group, for reports
- **Certificates with verification codes**

## How certificate codes work

Each code is a keyed hash (HMAC-SHA-256) of the name, course and date, written with letters that are easy to read aloud. Changing any detail breaks the code, and without the secret key nobody can make a valid one. The check page confirms a code, and a certificate can be withdrawn.

The secret key lives in the data file, so anyone who copies that file can make certificates. Keep it safe. The check page runs on your own computer, so an employer cannot check a code online unless you host it.

## An honest note on results

A rise in scores from one group, with no comparison group, does not prove the training caused it. People also learn from taking a test twice. The app says this beside the numbers, and donor reports should too.

## How it is tested

Tests confirm that any changed detail breaks a code, and that a tampered database record fails the check. Gain figures are tested by hand, and p-values match SciPy, when it is installed, on 50 random cases. App tests run the whole flow, and issuing twice changes nothing.

## Limits

One computer, one secret key, and no logins. The certificate layout is plain, and printing relies on the browser. This file holds personal data, and it is not encrypted.

## Tests

```
python -m unittest discover -s tests
```

MIT licence.
