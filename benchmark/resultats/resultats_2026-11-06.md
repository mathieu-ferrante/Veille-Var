# Résultats du benchmark – 2026-11-06

| Service | Modèle | JSON conforme (F4) | Exactitude classement (F1) | Écart pertinence (F2) | Résumés en français (F3) | Latence moy. / p95 | Tokens | Coût estimé | Erreurs de service |
|---|---|---|---|---|---|---|---|---|---|
| Mistral AI – La Plateforme | ministral-8b-latest | 100.0 % | 73.3 % | 0.33 | 100.0 % | 2.43 s / 3.53 s | 26238 | – | 0 |
| Google Gemini API | gemini-3.5-flash-lite | 100.0 % | 66.7 % | 0.53 | 100.0 % | 1.28 s / 3.03 s | 26580 | – | 0 |
| Modèle local (Ollama) | gemma3:12b | 100.0 % | 73.3 % | 0.97 | 100.0 % | 5.66 s / 8.69 s | 26000 | – | 0 |

Lecture : F4 en pourcentage des réponses reçues ; F1 et F3 en pourcentage des réponses conformes ; F2 = écart absolu moyen entre la note du modèle et l'annotation humaine (0 = parfait). Les erreurs de service (quota, réseau) ne sont pas imputées au modèle. La fidélité des résumés se juge à la relecture des fichiers bruts (`resultats/brut/`).
