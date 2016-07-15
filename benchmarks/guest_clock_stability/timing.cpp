/* Copyright 2016 The Android Open Source Project
 *
 * This software is licensed under the terms of the GNU General Public
 * License version 2, as published by the Free Software Foundation, and
 * may be copied, distributed, and modified under those terms.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
*/

#include <chrono>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iostream>
#include <unistd.h>
#include <vector>

#include <fcntl.h>
#include <linux/rtc.h>
#include <sys/ioctl.h>

using std::cout;
using std::ofstream;
using std::vector;

using hires_clock = std::chrono::high_resolution_clock;

int main() {
// Defined vars are used to select the correct clock for this run
#if defined(RTC)
  int rtc_fd = open("/dev/rtc1", O_RDONLY);
  if (rtc_fd < 0) {
    cout << "Error: RTC open failed\n";
    return 1;
  }

  tm tmm;
  time_t time;
  vector<tm> timestamps;
#elif defined(TIME)
  vector<long long> timestamps;
#elif defined(KVM)
  timespec time;
  constexpr long sec_to_nsec = pow(10, 9);
  vector<timespec> timestamps;
#endif

  size_t i = 1 << 18;
  timestamps.reserve(i);
  while (i--) {
#if defined(RTC)
    if (ioctl(rtc_fd, RTC_RD_TIME, &tmm) < 0) {
      cout << "Error: RTC read failed\n";
      return 1;
    }

    timestamps.push_back(tmm);
#elif defined(TIME)
    timestamps.push_back(hires_clock::now().time_since_epoch().count());
#elif defined(KVM)
    if (clock_gettime(CLOCK_REALTIME, &time) < 0) {
      cout << "Error: KVM read failed\n";
      return 1;
    }

    timestamps.push_back(time);
#endif
  }

  ofstream out("logs.txt");
  for (auto& tstamp : timestamps) {
#if defined(RTC)
    out << mktime(&tstamp) << "\n";
#elif defined(TIME)
    out << tstamp << "\n";
#elif defined(KVM)
    out << static_cast<long long> (tstamp.tv_sec) * sec_to_nsec
        + tstamp.tv_nsec << "\n";
#endif
  }

#if defined(RTC)
  close(rtc_fd);
#endif

  return 0;
}
