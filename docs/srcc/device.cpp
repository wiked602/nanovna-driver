#include "device.hpp"

#include <charconv>
#include <cmath>
#include <iostream>
#include <system_error>

namespace maturo {

void Log(const char* action, const std::string& error) {
  std::cerr << "module=maturo_at action=" << action << " device_id=maturo_at error=" << error
            << '\n';
}

void ValidateHeight(double cm) {
  if (!std::isfinite(cm)) throw DeviceError(Err::InvalidArgument, "height is not finite");
  if (cm < kMinCm || cm > kMaxCm)
    throw DeviceError(Err::InvalidArgument, "height out of range 100..400");
}

std::string FormatSetHeight(double cm) {
  // Округление до 0.1; to_chars не зависит от локали (разделитель всегда точка).
  const double rounded = std::round(cm * 10.0) / 10.0;
  char buf[32];
  const auto res = std::to_chars(buf, buf + sizeof buf, rounded, std::chars_format::fixed, 1);
  return "LD " + std::string(buf, res.ptr) + " CM NP GO";
}

Status ParseBusy(std::string_view s) {
  if (s == "0") return Status::Ready;
  if (s == "1") return Status::Busy;
  throw DeviceError(Err::Internal, "bad BU reply: " + std::string(s));
}

double ParseHeight(std::string_view s) {
  double v = 0.0;
  const char* end = s.data() + s.size();
  const auto [ptr, ec] = std::from_chars(s.data(), end, v);
  if (ec != std::errc() || ptr != end || !std::isfinite(v))
    throw DeviceError(Err::Internal, "bad RP reply: " + std::string(s));
  return v;
}

namespace {
// Эмулятор мачты отвечает "Maturo_Control_Module,AAT,v0.0.1"; стол - "... TT,...".
bool LooksLikeMast(const std::string& idn) { return idn.find("AAT") != std::string::npos; }
bool IsLost(const DeviceError& e) { return e.code == Err::Unavailable || e.connection_lost; }
}  // namespace

// ---------------- подключение и heartbeat ----------------

bool MastDevice::Connect() {
  std::lock_guard<std::mutex> lock(m_);
  return ConnectLocked();
}

bool MastDevice::ConnectLocked() {
  connected_ = false;
  t_.Close();
  try {
    t_.Connect();
    const std::string idn = t_.Query("*IDN?");
    if (!LooksLikeMast(idn)) throw DeviceError(Err::Internal, "unexpected *IDN? reply: " + idn);
    t_.Write("LD 0 DV");  // ось мачты = 0
    t_.Write("ST");
    if (ParseBusy(t_.Query("BU")) != Status::Ready)
      throw DeviceError(Err::FailedPrecondition, "mast is not READY after stop");
  } catch (const DeviceError& e) {
    Log("connect", e.what());
    t_.Close();
    return false;
  }
  connected_ = true;  // после обрыва движение сам не возобновляю: жду нового SetHeight
  return true;
}

bool MastDevice::Heartbeat() {
  if (!connected_) return Connect();
  std::unique_lock<std::mutex> lock(m_, std::try_to_lock);
  if (!lock.owns_lock()) return true;  // идёт команда: связь используется, значит жива
  if (!connected_) return false;
  try {
    if (!LooksLikeMast(QueryLocked("*IDN?"))) Disconnect("heartbeat", "unexpected *IDN? reply");
  } catch (const DeviceError&) {
    // QueryLocked уже пометил обрыв и записал лог
  }
  return connected_;
}

void MastDevice::Shutdown() {
  std::lock_guard<std::mutex> lock(m_);
  if (connected_) {
    try {
      t_.Write("ST");
    } catch (const DeviceError& e) {
      Log("shutdown_stop", e.what());
    }
  }
  connected_ = false;
  t_.Close();
}

void MastDevice::Disconnect(const char* action, const std::string& why) {
  connected_ = false;
  t_.Close();
  Log(action, why);
}

void MastDevice::RequireConnected() const {
  if (!connected_) throw DeviceError(Err::Unavailable, "not connected to mast");
}

// ---------------- команды (все под m_) ----------------

std::string MastDevice::QueryLocked(const std::string& cmd) {
  try {
    return t_.Query(cmd);
  } catch (const DeviceError& e) {
    if (IsLost(e)) Disconnect("query", e.what());
    throw;
  }
}

void MastDevice::WriteLocked(const std::string& cmd) {
  try {
    t_.Write(cmd);
  } catch (const DeviceError& e) {
    if (IsLost(e)) Disconnect("write", e.what());
    throw;
  }
}

Status MastDevice::QueryStatusLocked() { return ParseBusy(QueryLocked("BU")); }

void MastDevice::SetHeight(double cm) {
  ValidateHeight(cm);                    // до любого обращения к TCP
  std::lock_guard<std::mutex> lock(m_);  // проверка статуса и запись - одним куском
  RequireConnected();
  if (QueryStatusLocked() != Status::Ready)
    throw DeviceError(Err::FailedPrecondition, "mast is busy");
  WriteLocked(FormatSetHeight(cm));  // setter: ответа нет
}

double MastDevice::GetHeight() {
  std::lock_guard<std::mutex> lock(m_);
  RequireConnected();
  return ParseHeight(QueryLocked("RP"));
}

Status MastDevice::GetStatus() {
  std::lock_guard<std::mutex> lock(m_);
  RequireConnected();
  return QueryStatusLocked();
}

void MastDevice::Stop() {
  std::lock_guard<std::mutex> lock(m_);
  RequireConnected();
  WriteLocked("ST");
}

}  // namespace maturo
