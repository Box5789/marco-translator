# Automatic learning policy

Runtime learning is deliberately asymmetric.

## May update automatically

- session context
- exact translation cache / TM
- user terminology from explicit corrections
- OCR correction profiles
- local routing weights
- reversible provisional user-overlay entries under strict thresholds

## Must not update automatically

- Base KG topology
- new global concepts
- deletion or redefinition of existing concepts
- global aliases
- domain-wide negative constraints
- changes affecting other users

The maintenance plane may propose these operations, but a user-approved validated patch is required.
