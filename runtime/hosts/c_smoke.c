#include "marco_runtime.h"
#include "fixture_cases.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define MAX_INPUT (1024u * 1024u)

static int fail(const char *message, const char *case_id) {
    fprintf(stderr, "FAIL %s%s%s\n", message, case_id ? ": " : "", case_id ? case_id : "");
    return 1;
}

static MarcoRuntimeStatus run_json(MarcoRuntime *runtime, const char *json, char **out) {
    *out = NULL;
    return marco_runtime_process_json(runtime, (const uint8_t *)json, strlen(json), out);
}

static int expect_output(MarcoRuntime *runtime, const char *json, const char *needle, const char *case_id) {
    char *output = NULL;
    MarcoRuntimeStatus status = run_json(runtime, json, &output);
    if (status != MARCO_RUNTIME_OK || output == NULL) return fail(marco_runtime_status_name(status), case_id);
    int matched = strstr(output, needle) != NULL;
    marco_runtime_string_free(output);
    return matched ? 0 : fail("expected response field missing", case_id);
}

static int check_boundaries(MarcoRuntime *runtime) {
    const uint8_t invalid_utf8[] = {0xff};
    const uint8_t invalid_json[] = "{";
    const uint8_t unsupported[] = "{\"contract_version\":\"marco-runtime.v2\",\"operation\":\"translate\"}";
    char *output = (char *)1;
    MarcoRuntime *invalid_handle = (MarcoRuntime *)1;
    if (marco_runtime_open(NULL, 0, &invalid_handle) != MARCO_RUNTIME_INVALID_ARGUMENT || invalid_handle != NULL) return fail("invalid runtime path was accepted", NULL);
    if (marco_runtime_open(invalid_utf8, sizeof(invalid_utf8), &invalid_handle) != MARCO_RUNTIME_INVALID_UTF8 || invalid_handle != NULL) return fail("invalid UTF-8 path was accepted", NULL);
    if (marco_runtime_process_json(runtime, invalid_utf8, sizeof(invalid_utf8), &output) != MARCO_RUNTIME_INVALID_UTF8 || output != NULL) return fail("invalid UTF-8 was accepted", NULL);
    if (marco_runtime_process_json(runtime, invalid_json, sizeof(invalid_json) - 1, &output) != MARCO_RUNTIME_INVALID_JSON || output != NULL) return fail("invalid JSON was accepted", NULL);
    if (marco_runtime_process_json(runtime, unsupported, sizeof(unsupported) - 1, &output) != MARCO_RUNTIME_UNSUPPORTED_CONTRACT || output != NULL) return fail("unsupported contract was accepted", NULL);
    const uint8_t unknown_field[] = "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"translate\",\"request\":{\"text\":\"x\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":null,\"style\":\"neutral\",\"session_id\":null,\"unexpected\":true}}";
    if (marco_runtime_process_json(runtime, unknown_field, sizeof(unknown_field) - 1, &output) != MARCO_RUNTIME_INVALID_REQUEST || output != NULL) return fail("unknown request field was accepted", NULL);
    uint8_t *oversized = (uint8_t *)malloc(MAX_INPUT + 1);
    if (!oversized) return fail("allocation failed", NULL);
    memset(oversized, ' ', MAX_INPUT + 1);
    MarcoRuntimeStatus oversized_status = marco_runtime_process_json(runtime, oversized, MAX_INPUT + 1, &output);
    free(oversized);
    if (oversized_status != MARCO_RUNTIME_INPUT_TOO_LARGE || output != NULL) return fail("oversized input was accepted", NULL);

    const char *large_prefix = "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"translate\",\"request\":{\"text\":\"";
    const char *large_suffix = "\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":null,\"style\":\"neutral\",\"session_id\":null}}";
    size_t text_len = 750000;
    size_t prefix_len = strlen(large_prefix), suffix_len = strlen(large_suffix);
    char *large_json = (char *)malloc(prefix_len + text_len + suffix_len + 1);
    if (!large_json) return fail("allocation failed", NULL);
    memcpy(large_json, large_prefix, prefix_len);
    memset(large_json + prefix_len, 'x', text_len);
    memcpy(large_json + prefix_len + text_len, large_suffix, suffix_len + 1);
    MarcoRuntimeStatus large_status = marco_runtime_process_json(runtime, (const uint8_t *)large_json, prefix_len + text_len + suffix_len, &output);
    free(large_json);
    if (large_status != MARCO_RUNTIME_OUTPUT_TOO_LARGE || output != NULL) return fail("oversized output was accepted", NULL);
    if (strcmp(marco_runtime_status_name(999), "unknown_status") != 0) return fail("invalid status was not handled", NULL);
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return fail("usage: p1f_smoke DATABASE_PATH", NULL);
    clock_t start = clock();
    MarcoRuntime *runtime = NULL;
    MarcoRuntimeStatus status = marco_runtime_open((const uint8_t *)argv[1], strlen(argv[1]), &runtime);
    if (status != MARCO_RUNTIME_OK || runtime == NULL) return fail(marco_runtime_status_name(status), "open");
    clock_t opened = clock();

    for (size_t i = 0; i < P1F_CASE_COUNT; i++) {
        char *output = NULL;
        status = run_json(runtime, p1f_cases[i].request, &output);
        if (status != MARCO_RUNTIME_OK || output == NULL) {
            marco_runtime_close(runtime);
            return fail(marco_runtime_status_name(status), p1f_cases[i].id);
        }
        for (unsigned field = 0; field < p1f_cases[i].check_count; field++) {
            if (!strstr(output, p1f_cases[i].checks[field])) {
                marco_runtime_string_free(output);
                marco_runtime_close(runtime);
                return fail("fixture field mismatch", p1f_cases[i].id);
            }
        }
        marco_runtime_string_free(output);
    }
    if (check_boundaries(runtime)) { marco_runtime_close(runtime); return 1; }

    const char *add_term = "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"add_terminology\",\"source\":\"portable-term\",\"target\":\"용어\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":null,\"concept\":\"PORTABLE_TERM\",\"confidence\":1.0,\"origin\":\"user\"}";
    char *added = NULL;
    if (run_json(runtime, add_term, &added) != MARCO_RUNTIME_OK || !added) { marco_runtime_close(runtime); return fail("terminology write failed", NULL); }
    marco_runtime_string_free(added);
    if (expect_output(runtime,
        "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"translate\",\"request\":{\"text\":\"portable-term\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":null,\"style\":\"neutral\",\"session_id\":null}}",
        "\"translated_text\":\"용어\"", "overlay-roundtrip")) { marco_runtime_close(runtime); return 1; }

    const char *bind_session = "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"bind_session_entity\",\"session_id\":\"p1f-smoke\",\"source\":\"西边有狙\",\"target\":\"임시 결과\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":\"gaming\",\"concept\":\"SESSION_TERM\"}";
    char *bound = NULL;
    if (run_json(runtime, bind_session, &bound) != MARCO_RUNTIME_OK || !bound) { marco_runtime_string_free(bound); marco_runtime_close(runtime); return fail("session bind failed", NULL); }
    marco_runtime_string_free(bound);
    if (expect_output(runtime,
        "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"translate\",\"request\":{\"text\":\"西边有狙\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":\"gaming\",\"style\":\"neutral\",\"session_id\":\"p1f-smoke\"}}",
        "\"translated_text\":\"임시 결과\"", "session-precedence")) { marco_runtime_close(runtime); return 1; }

    const char *correct = "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"correct\",\"request\":{\"text\":\"memory-source\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":null,\"style\":\"neutral\",\"session_id\":null},\"corrected_text\":\"기억 번역\",\"generated_text\":null}";
    char *correction = NULL;
    if (run_json(runtime, correct, &correction) != MARCO_RUNTIME_OK || !strstr(correction, "\"tm_written\":true")) { marco_runtime_string_free(correction); marco_runtime_close(runtime); return fail("correction write failed", NULL); }
    marco_runtime_string_free(correction);
    if (expect_output(runtime,
        "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"translate\",\"request\":{\"text\":\"memory-source\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":null,\"style\":\"neutral\",\"session_id\":null}}",
        "\"path\":\"tm\"", "tm-roundtrip")) { marco_runtime_close(runtime); return 1; }

    marco_runtime_close(runtime);
    runtime = NULL;
    status = marco_runtime_open((const uint8_t *)argv[1], strlen(argv[1]), &runtime);
    if (status != MARCO_RUNTIME_OK || runtime == NULL) return fail(marco_runtime_status_name(status), "reopen");
    if (expect_output(runtime,
        "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"translate\",\"request\":{\"text\":\"西边有狙\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":\"gaming\",\"style\":\"neutral\",\"session_id\":\"p1f-smoke\"}}",
        "\"translated_text\":\"서쪽에 저격수 있음\"", "session-ephemeral")) { marco_runtime_close(runtime); return 1; }
    if (expect_output(runtime,
        "{\"contract_version\":\"marco-runtime.v1\",\"operation\":\"translate\",\"request\":{\"text\":\"memory-source\",\"source_language\":\"zh\",\"target_language\":\"ko\",\"domain\":null,\"style\":\"neutral\",\"session_id\":null}}",
        "\"translated_text\":\"기억 번역\"", "persistent-reopen")) { marco_runtime_close(runtime); return 1; }

    clock_t done = clock();
    marco_runtime_close(runtime);
    double open_us = 1000000.0 * (double)(opened - start) / (double)CLOCKS_PER_SEC;
    double total_us = 1000000.0 * (double)(done - opened) / (double)CLOCKS_PER_SEC;
    printf("P1F_REPORT contract=%s fixture_sha256=%s fixture_cases=%zu network_dependency=none open_cpu_us=%.0f smoke_cpu_us=%.0f\n",
        P1F_CONTRACT_VERSION, P1F_FIXTURE_SHA256, (size_t)P1F_CASE_COUNT, open_us, total_us);
    return 0;
}
