#include <iostream>
#include <fstream>
#include <vector>
#include <cmath>
#include <numeric>
#include <limits>
#include "json.hpp"  // nlohmann json single header

using json = nlohmann::json;

// ---------- CONFIG — canonical 35-feature order (mirrors feature_schema.py CANONICAL_FEATURE_ORDER) ----------
static const std::vector<std::string> FEATURE_ORDER = {
    "open", "high", "low", "close", "volume",
    "volume_ratio", "double_sweep",
    "ema_fast", "ema_slow", "ema_spread",
    "trend_bias", "trend_strength",
    "momentum_score",
    "atr", "volatility_ratio",
    "rsi_14",
    "macd_line", "macd_signal", "macd_hist",
    "sweep_detected", "liquidity_sweep", "break_of_structure",
    "swing_high", "swing_low", "higher_high", "lower_low",
    "body_size", "wick_size", "body_ratio",
    "volatility_regime",
    "session", "hour_of_day",
    "disp_strength", "retest_depth", "candles_since_retest"
};

inline float clean(float x) {
    if (std::isnan(x) || std::isinf(x)) return 0.0f;
    return x;
}

std::vector<float> normalize(const json& r) {
    std::vector<float> x(FEATURE_ORDER.size(), 0.0f);

    for (size_t i = 0; i < FEATURE_ORDER.size(); ++i) {
        const auto& k = FEATURE_ORDER[i];
        float v = 0.0f;

        if (r.contains(k) && r[k].is_number()) {
            v = static_cast<float>(r[k].get<double>());
        } else if (r.contains(k) && r[k].is_null()) {
            v = std::numeric_limits<float>::quiet_NaN();
        }

        x[i] = clean(v);
    }
    return x;
}

std::vector<float> binarize(const std::vector<float>& x) {
    std::vector<float> xb(x.size());
    for (size_t i = 0; i < x.size(); ++i) {
        xb[i] = (x[i] > 0.0f) ? 1.0f : -1.0f;  // zero -> -1
    }
    return xb;
}

float dot(const std::vector<float>& w, const std::vector<float>& x) {
    // identical accumulation style to Python np.dot
    return std::inner_product(w.begin(), w.end(), x.begin(), 0.0f);
}

std::vector<float> matvec(const std::vector<std::vector<int>>& W,
                         const std::vector<float>& x) {
    // W is int8 {-1, +1}, convert on the fly to float
    std::vector<float> out(W.size(), 0.0f);
    for (size_t i = 0; i < W.size(); ++i) {
        float acc = 0.0f;
        for (size_t j = 0; j < x.size(); ++j) {
            acc += static_cast<float>(W[i][j]) * x[j];
        }
        out[i] = acc;
    }
    return out;
}

std::vector<float> add_bias_scale(const std::vector<float>& v,
                                  const std::vector<float>& b,
                                  float scale) {
    std::vector<float> out(v.size(), 0.0f);
    for (size_t i = 0; i < v.size(); ++i) {
        out[i] = v[i] * scale + b[i];
    }
    return out;
}

// sigmoid for final layer (if you want exact parity with Python runner using sigmoid)
inline float sigmoid(float z) {
    return 1.0f / (1.0f + std::exp(-z));
}

int main() {
    // ---------- LOAD INPUTS ----------
    std::ifstream f_in("test_vectors.json");
    if (!f_in) {
        std::cerr << "Cannot open test_vectors.json\n";
        return 1;
    }
    json data; f_in >> data;

    std::ifstream f_model("model.json");
    if (!f_model) {
        std::cerr << "Cannot open model.json\n";
        return 1;
    }
    json model; f_model >> model;

    // model fields expected:
    // model["weights"] -> [ [ [int] * in ] * out ] per layer
    // model["bias"]    -> [ [float] * out ] per layer
    // model["scales"]  -> [ float per layer ]

    const auto& weights = model["weights"];
    const auto& bias    = model["bias"];
    const auto& scales  = model["scales"];

    json outputs = json::array();

    // ---------- RUN ----------
    for (const auto& rec : data) {
        // normalize → binarize
        std::vector<float> x = normalize(rec);
        x = binarize(x);

        // LAYER 1
        std::vector<std::vector<int>> W1 = weights[0].get<std::vector<std::vector<int>>>();
        std::vector<float> b1 = bias[0].get<std::vector<float>>();
        float s1 = static_cast<float>(scales[0].get<double>());

        std::vector<float> z1 = matvec(W1, x);
        std::vector<float> a1 = add_bias_scale(z1, b1, s1);

        // LAYER 2
        std::vector<std::vector<int>> W2 = weights[1].get<std::vector<std::vector<int>>>();
        std::vector<float> b2 = bias[1].get<std::vector<float>>();
        float s2 = static_cast<float>(scales[1].get<double>());

        std::vector<float> z2 = matvec(W2, a1);
        std::vector<float> a2 = add_bias_scale(z2, b2, s2);

        // LAYER 3 (final)
        std::vector<std::vector<int>> W3 = weights[2].get<std::vector<std::vector<int>>>();
        std::vector<float> b3 = bias[2].get<std::vector<float>>();
        float s3 = static_cast<float>(scales[2].get<double>());

        std::vector<float> z3 = matvec(W3, a2);
        std::vector<float> a3 = add_bias_scale(z3, b3, s3);

        float final_val = a3[0];        // if Python uses raw
        // float final_val = sigmoid(a3[0]); // enable if Python uses sigmoid

        json row;
        row["layer1"] = a1;
        row["layer2"] = a2;
        row["final"]  = final_val;

        outputs.push_back(row);
    }

    // ---------- SAVE ----------
    std::ofstream f_out("cpp_outputs.json");
    f_out << outputs.dump(2);

    std::cout << "C++ parity run complete.\n";
    return 0;
}