#ifndef MARCO_RUNTIME_H
#define MARCO_RUNTIME_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct MarcoRuntime MarcoRuntime;
typedef int32_t MarcoRuntimeStatus;

#define MARCO_RUNTIME_OK 0
#define MARCO_RUNTIME_INVALID_ARGUMENT 1
#define MARCO_RUNTIME_INPUT_TOO_LARGE 2
#define MARCO_RUNTIME_INVALID_UTF8 3
#define MARCO_RUNTIME_INVALID_JSON 4
#define MARCO_RUNTIME_UNSUPPORTED_CONTRACT 5
#define MARCO_RUNTIME_INVALID_REQUEST 6
#define MARCO_RUNTIME_UNSUPPORTED_STORE_VERSION 7
#define MARCO_RUNTIME_INCOMPATIBLE_STORE 8
#define MARCO_RUNTIME_STORAGE_ERROR 9
#define MARCO_RUNTIME_NOT_FOUND 10
#define MARCO_RUNTIME_INVALID_STATE 11
#define MARCO_RUNTIME_OUTPUT_TOO_LARGE 12
#define MARCO_RUNTIME_INTERNAL_ERROR 13

MarcoRuntimeStatus marco_runtime_open(const uint8_t *path, size_t path_len, MarcoRuntime **out_runtime);
MarcoRuntimeStatus marco_runtime_process_json(
    MarcoRuntime *runtime, const uint8_t *input, size_t input_len, char **out_json);
void marco_runtime_close(MarcoRuntime *runtime);
void marco_runtime_string_free(char *json);
const char *marco_runtime_status_name(int32_t status);

#ifdef __cplusplus
}
#endif
#endif
