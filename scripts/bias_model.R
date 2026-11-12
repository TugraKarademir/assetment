# Yanlılık analizi: makine puanlarının yanıt özelliklerine (uzunluk, yazım hatası, sözcük çeşitliliği)
# ve Bloom basamağına göre sistematik sapma gösterip göstermediği.
#
# Girdi : results/bias/bias_data_total.csv      (scoring export-bias-data)
#         results/bias/bias_data_criterion.csv
# Paketler: install.packages(c("lme4", "lmerTest", "ordinal", "dplyr", "readr"))
#
# Model 1 (toplam puan, doğrusal karma model):
#   fark = makine − insan uzlaşı puanı
#   fark ~ z(log kelime) + z(yazım hatası oranı) + z(MATTR) + soru (sabit) + (1 | öğrenci)
#   Bloom basamağı soru düzeyinde bir değişken olduğundan soru sabit etkisiyle tam eşdoğrusaldır;
#   Bloom etkisi Model 1b'de soru yerine Bloom girilerek ve özelliklerle etkileşimiyle sınanır.
# Model 2 (ölçüt puanı, sıralı karma model):
#   makine puanı (sıralı) ~ insan puanı + z(log kelime) + z(yazım) + z(MATTR) + soru + (1 | öğrenci)
#   İnsan puanı sabit tutulduğunda özelliklerin katsayısı ≠ 0 ise makine o özelliğe insanlardan farklı tepki veriyordur.

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(lme4); library(lmerTest); library(ordinal)
})

tot  <- read_csv("results/bias/bias_data_total.csv", show_col_types = FALSE)
crit <- read_csv("results/bias/bias_data_criterion.csv", show_col_types = FALSE)

z <- function(x) as.numeric(scale(x))
prep <- function(d) d %>% mutate(
  student_code = factor(student_code), item_id = factor(item_id), bloom = factor(bloom),
  z_len = z(log1p(n_words)), z_spell = z(spelling_error_rate), z_div = z(mattr))

tot <- prep(tot); crit <- prep(crit)
conditions <- grep("^score__", names(tot), value = TRUE)
cat("Koşullar:", paste(sub("^score__", "", conditions), collapse = ", "), "\n\n")

results <- list()
for (cond in conditions) {
  d <- tot %>% mutate(diff = .data[[cond]] - human_score) %>% filter(!is.na(diff), !is.na(z_spell), !is.na(z_div))
  if (nrow(d) < 20) next
  # Öğrenci başına tek yanıt varsa rastgele etki tahmin edilemez -> uyar
  m1 <- tryCatch(lmer(diff ~ z_len + z_spell + z_div + item_id + (1 | student_code), data = d),
                 error = function(e) { message(cond, ": ", conditionMessage(e)); NULL })
  if (!is.null(m1)) {
    cf <- summary(m1)$coefficients
    for (term in c("z_len", "z_spell", "z_div")) {
      results[[length(results) + 1]] <- data.frame(condition = sub("^score__", "", cond), model = "lmer_diff",
        term = term, estimate = cf[term, "Estimate"], se = cf[term, "Std. Error"], p = cf[term, "Pr(>|t|)"],
        singular = isSingular(m1))
    }
  }
  m1b <- tryCatch(lmer(diff ~ (z_len + z_spell + z_div) * bloom + (1 | student_code), data = d),
                  error = function(e) NULL)
  if (!is.null(m1b)) {
    cf <- summary(m1b)$coefficients
    for (term in grep("bloom", rownames(cf), value = TRUE)) {
      results[[length(results) + 1]] <- data.frame(condition = sub("^score__", "", cond), model = "lmer_diff_bloom",
        term = term, estimate = cf[term, "Estimate"], se = cf[term, "Std. Error"], p = cf[term, "Pr(>|t|)"],
        singular = isSingular(m1b))
    }
  }
  dc <- crit %>% filter(!is.na(.data[[cond]]), !is.na(z_spell), !is.na(z_div)) %>%
    mutate(y = factor(.data[[cond]], ordered = TRUE))
  m2 <- tryCatch(clmm(y ~ human_score + z_len + z_spell + z_div + item_id + (1 | student_code), data = dc,
                      link = "logit", Hess = TRUE),
                 error = function(e) { message(cond, " (clmm): ", conditionMessage(e)); NULL })
  if (!is.null(m2)) {
    cf <- summary(m2)$coefficients
    for (term in c("human_score", "z_len", "z_spell", "z_div")) {
      results[[length(results) + 1]] <- data.frame(condition = sub("^score__", "", cond), model = "clmm_ordinal",
        term = term, estimate = cf[term, "Estimate"], se = cf[term, "Std. Error"], p = cf[term, "Pr(>|z|)"],
        singular = NA)
    }
  }
}

out <- bind_rows(results)
write_csv(out, "results/bias/bias_model_coefficients.csv")
print(head(as.data.frame(out %>% mutate(across(where(is.numeric), ~ round(.x, 3)))), 60), row.names = FALSE)
cat("\nYazıldı: results/bias/bias_model_coefficients.csv\n")
cat("Not: altın sette çoğu öğrencinin tek yanıtı varsa öğrenci varyansı sıfıra yakın (singular) çıkabilir;\n",
    "tüm set üzerinde (resmî not ile) aynı model daha fazla öğrenci-içi tekrar sağlar.\n")
