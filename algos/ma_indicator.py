# Berechnet den MA, lückenlose Up/Down-Masken und Signale.
    def apply(self, df: pd.DataFrame, generate_signals: bool = False) -> pd.DataFrame:
        out = df.copy()
        vol = out["volume"] if "volume" in out.columns else None

        # 1. MA berechnen
        col_name = f"ma_{self.ma_type.lower()}_{self.period}"
        ma_series = self.calculate(out["close"], volume=vol)
        out[col_name] = ma_series

        # 2. Steigung bestimmen
        diff = ma_series.diff()
        is_up = diff >= 0
        if len(is_up) > 1:
            is_up.iloc[0] = is_up.iloc[1]

        # 3. Masken mit Nahtstelle am Wendepunkt
        is_up_prev = is_up.shift(1).fillna(is_up.iloc[0])
        bull_mask = is_up | is_up_prev
        bear_mask = (~is_up) | (~is_up_prev)

        # WICHTIG: None statt np.nan verhindert das Überbrücken von Lücken in LWC
        out[f"{col_name}_bull"] = ma_series.where(bull_mask, np.nan)
        out[f"{col_name}_bear"] = ma_series.where(bear_mask, np.nan)

        # 4. Signale nur bei Bedarf
        if generate_signals:
            prev_diff = diff.shift(1)
            buy_cond = (diff > 0) & (prev_diff <= 0)
            sell_cond = (diff < 0) & (prev_diff >= 0)
            out["signal"] = np.select([buy_cond, sell_cond], [1, -1], default=0)
        elif "signal" in out.columns:
            out = out.drop(columns=["signal"])

        return out