/*
 * Copyright (C) 2016 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <string.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <algorithm>
#include <vector>
#include <errno.h>
#include <cassert>

// iobench -seq -write 1024 - sequentially write 1024MB to /tmp/iobench.dat
// iobench -rand -write 1024 - sequentially write 1024MB (in 256K chunks) to
// /tmp/iobench.dat
// iobench -seq -read 1024 - sequentially read 1024MB from /tmp/iobench.dat
// iobench -rand -read 1024 - sequentially read 1024MB (in 256K chunks) from
// /tmp/iobench.dat

#ifdef __ANDROID__
#define TMP_DIR "/data/local/tmp"
#else  // __linux__
#define TMP_DIR "/tmp"
#endif

#define DATA_FILE TMP_DIR "/iobench.dat"

// Allocate a buffer of size |buffer_size|.  Fill it with
// non-zero data to prevent sparse files from being created
void* mallocNoise(size_t buffer_size) {
    void* result = malloc(buffer_size);
    for (int i = 0; i < buffer_size; i += 512) {
        int* block = (int*)((char*)result + i);
        *block = i + 1;
    }
    return result;
}

// We want to test random file access but we want to make sure that
// every read/write chunk is read/written exactly once.
// So we make a sequential list of chunk indexes and shuffle it
std::vector<size_t> createRandomChunkList(size_t chunk_count) {
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<size_t> dist(0, chunk_count-1);

    std::vector<size_t> result(chunk_count);

    // a sequential list of chunk indexes
    for (int64_t i = 0; i < chunk_count; i++) {
        result[i] = i;
    }

    // shuffle the list of chunk indexes
    // swap every chunk with a random chunk
    std::shuffle(result.begin(), result.end(), gen);

    return result;
}

const int NS_PER_SEC = 1000 * 1000 * 1000;

int64_t subtractTimespec(const struct timespec* hi, const struct timespec* lo) {
    int64_t delta = hi->tv_sec - lo->tv_sec;
    delta *= NS_PER_SEC;
    delta += hi->tv_nsec;
    delta -= lo->tv_nsec;
    return delta;
}

int main(int argc, const char* argv[]) {
    const size_t kBufferSize = 256 * 1024;
    bool read_mode = false;
    size_t chunk_size = kBufferSize;
    bool rand_mode = false;
    size_t file_size_mb = 1024;
    for (int i = 1; i < argc; i++) {
        if (strcmp("-rand", argv[i]) == 0) {
            rand_mode = true;
            chunk_size = 4 * 1024;
        } else if (strcmp("-seq", argv[i]) == 0) {
            rand_mode = false;
            chunk_size = kBufferSize;
        } else if (strcmp("-read", argv[i]) == 0) {
            read_mode = true;
        } else if (strcmp("-write", argv[i]) == 0) {
            read_mode = false;
        } else {
            file_size_mb = strtoul(argv[i], nullptr, 10);
        }
    }

    size_t file_size = file_size_mb * 1024 * 1024;
    size_t chunk_count = file_size / chunk_size;
    std::vector<size_t> chunk_list = createRandomChunkList(chunk_count);

    int open_flags = O_CREAT;
    if (read_mode) {
        open_flags |= O_RDONLY;
    } else {
        open_flags |= O_WRONLY;
    }
    int fd = open(DATA_FILE, open_flags, 0600);
    if (fd < 0) {
        perror("open");
        return -1;
    }
    void* buffer = mallocNoise(kBufferSize);

    struct timespec start;
    if (clock_gettime(CLOCK_REALTIME, &start) < 0) {
        perror("clock_gettime");
        return -1;
    }

    for (int i = 0; i < chunk_count; i++) {
        if (rand_mode) {
            off64_t off = chunk_list[i] * chunk_size;
            off64_t result = lseek64(fd, off, SEEK_SET);
            if (result != off) {
                perror("lseek64");
                return -1;
            }
        }
        if (read_mode) {
            ssize_t read_result = read(fd, buffer, chunk_size);
            if (chunk_size != read_result) {
                perror("read");
                return -1;
            }
        } else {
            if (chunk_size != write(fd, buffer, chunk_size)) {
                perror("write");
                return -1;
            }
        }
    }

    if (!read_mode) {
        if (fsync(fd) < 0) {
            perror("fsync");
            return -1;
        }
    }

    if (close(fd) < 0) {
        perror("close");
        return -1;
    }

    struct timespec end;
    if (clock_gettime(CLOCK_REALTIME, &end) < 0) {
        perror("clock_gettime");
        return -1;
    }
    int64_t elapsed_ns = subtractTimespec(&end, &start);
#ifdef DEBUG
    printf("start sec %li nsec %li\n", start.tv_sec, start.tv_nsec);
    printf("end   sec %li nsec %li\n", end.tv_sec, end.tv_nsec);
    printf("megabytes: %zu\n", file_size_mb);
    printf("time elapsed: %lins\n", elapsed_ns);
    printf("time elapsed: %fs\n", (double)elapsed_ns / (double)NS_PER_SEC);
#endif
    if (elapsed_ns > 0) {
        double megabytes_per_second =
                (double) file_size_mb * (double) NS_PER_SEC / (double) elapsed_ns;
        printf("%.2fMB/s\n", megabytes_per_second);
    }
    else {
        printf("elapsed_ns == 0\n");
    }
    return 0;
}
