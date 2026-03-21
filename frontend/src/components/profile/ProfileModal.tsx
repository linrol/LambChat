import { createPortal } from "react-dom";
import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Eye,
  EyeOff,
  Loader2,
  X,
  Pencil,
  Check,
  Save,
  AlertCircle,
} from "lucide-react";
import { toast } from "react-hot-toast";
import { useAuth } from "../../hooks/useAuth";
import { useBrowserNotification } from "../../hooks/useBrowserNotification";
import { useVersion } from "../../hooks/useVersion";
import { Permission, User, AgentInfo } from "../../types";
import {
  authApi,
  uploadApi,
  agentConfigApi,
  agentApi,
} from "../../services/api";
import { LoadingSpinner } from "../common/LoadingSpinner";

interface ProfileModalProps {
  showProfileModal: boolean;
  onCloseProfileModal: () => void;
  versionInfo: ReturnType<typeof useVersion>["versionInfo"];
}

export function ProfileModal({
  showProfileModal,
  onCloseProfileModal,
  versionInfo,
}: ProfileModalProps) {
  const { t } = useTranslation();
  const { user, refreshUser, hasPermission } = useAuth();
  const [userData, setUserData] = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState<
    "info" | "password" | "notification" | "agent"
  >("info");
  const [isLoading, setIsLoading] = useState(false);

  // Username change state
  const [isEditingUsername, setIsEditingUsername] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [usernameError, setUsernameError] = useState("");
  const [isUpdatingUsername, setIsUpdatingUsername] = useState(false);

  // Password change state
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  // Avatar upload state
  const [isUploading, setIsUploading] = useState(false);
  const [imgError, setImgError] = useState(false);

  // Permission check for avatar upload
  const canUploadAvatar = hasPermission(Permission.AVATAR_UPLOAD);

  // Browser notification
  const {
    requestPermission,
    isSupported,
    permission,
    isMobile,
    isMobileNotificationSupported,
  } = useBrowserNotification();

  // Sync user data when modal opens or user changes
  useEffect(() => {
    if (showProfileModal && user) {
      setUserData(user);
    }
  }, [showProfileModal, user]);

  // Reset state when modal opens
  useEffect(() => {
    if (showProfileModal) {
      setActiveTab("info");
      setIsEditingUsername(false);
      setNewUsername("");
      setUsernameError("");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordError("");
      setPasswordSuccess(false);
    }
  }, [showProfileModal]);

  // Body scroll lock
  useEffect(() => {
    if (showProfileModal) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [showProfileModal]);

  // ESC key to close
  useEffect(() => {
    if (!showProfileModal) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseProfileModal();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [showProfileModal, onCloseProfileModal]);

  // Compress image file to target size (default 100KB)
  const compressImage = async (
    file: File,
    targetSizeKB: number = 100,
    maxWidth: number = 512,
    maxHeight: number = 512,
  ): Promise<File> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        // Calculate new dimensions while maintaining aspect ratio
        let { width, height } = img;
        if (width > maxWidth || height > maxHeight) {
          const ratio = Math.min(maxWidth / width, maxHeight / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }

        // Create canvas and draw image
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("Failed to get canvas context"));
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);

        // Try different quality levels to meet target size
        const targetBytes = targetSizeKB * 1024;
        let quality = 0.9;
        const minQuality = 0.1;

        const tryCompress = (): void => {
          canvas.toBlob(
            (blob) => {
              if (!blob) {
                reject(new Error("Failed to compress image"));
                return;
              }

              // If size is within target or we've reached minimum quality
              if (blob.size <= targetBytes || quality <= minQuality) {
                const compressedFile = new File([blob], file.name, {
                  type: "image/jpeg",
                  lastModified: Date.now(),
                });
                resolve(compressedFile);
                return;
              }

              // Reduce quality and try again
              quality -= 0.1;
              tryCompress();
            },
            "image/jpeg",
            quality,
          );
        };

        tryCompress();
      };

      img.onerror = () => {
        reject(new Error("Failed to load image"));
      };

      img.src = URL.createObjectURL(file);
    });
  };

  // Handle avatar upload
  // Note: Avatar is stored as base64 in database, no S3 required
  const handleAvatarUpload = async (file: File) => {
    setIsUploading(true);
    try {
      // Compress image to under 100KB before uploading
      const compressedFile = await compressImage(file, 100, 512, 512);

      // Upload avatar (stored as base64 in database)
      await uploadApi.uploadAvatar(compressedFile);
      // Refresh user data in both local state and global auth context
      const user = await authApi.getProfile();
      setUserData(user);
      // Update global auth context to refresh avatar in header/sidebar
      refreshUser();
    } catch (error) {
      console.error("Failed to upload avatar:", error);
      const message = error instanceof Error ? error.message : "Upload failed";
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  };

  // Handle avatar delete
  const handleAvatarDelete = async () => {
    setIsUploading(true);
    try {
      await uploadApi.deleteAvatar();
      // Refresh user data in both local state and global auth context
      const user = await authApi.getProfile();
      setUserData(user);
      // Update global auth context to refresh avatar in header/sidebar
      refreshUser();
      toast.success(t("profile.avatarDeleted"));
    } catch (error) {
      console.error("Failed to delete avatar:", error);
      const message = error instanceof Error ? error.message : "Delete failed";
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  };

  // Handle username update
  const handleUsernameUpdate = async () => {
    setUsernameError("");

    if (!newUsername || newUsername.length < 3 || newUsername.length > 50) {
      setUsernameError(t("profile.usernameLengthError"));
      return;
    }

    setIsUpdatingUsername(true);
    try {
      const updatedUser = await authApi.updateUsername(newUsername);
      setUserData(updatedUser);
      // Refresh global auth context
      refreshUser();
      setIsEditingUsername(false);
      setNewUsername("");
      toast.success(t("profile.usernameUpdated"));
    } catch (error) {
      setUsernameError(
        (error as Error).message || t("profile.usernameUpdateFailed"),
      );
    } finally {
      setIsUpdatingUsername(false);
    }
  };

  // Handle password change
  const handlePasswordChange = async () => {
    setPasswordError("");
    setPasswordSuccess(false);

    if (!oldPassword || !newPassword || !confirmPassword) {
      setPasswordError(
        t("profile.oldPassword") +
          ", " +
          t("profile.newPassword") +
          ", " +
          t("profile.confirmPassword") +
          " required",
      );
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError(t("auth.validation.passwordMismatch"));
      return;
    }

    if (newPassword.length < 6) {
      setPasswordError(t("auth.validation.passwordMinLength"));
      return;
    }

    setIsLoading(true);
    try {
      await authApi.changePassword(oldPassword, newPassword);
      setPasswordSuccess(true);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      setPasswordError(
        (error as Error).message || t("profile.passwordChangeFailed"),
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (!showProfileModal) return null;

  const tabs: { key: typeof activeTab; label: string }[] = [
    { key: "info", label: t("profile.title") },
    { key: "password", label: t("profile.changePassword") },
    { key: "notification", label: t("profile.notifications") },
    { key: "agent", label: t("agentConfig.defaultAgent") },
  ];

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-end sm:items-center sm:justify-center"
      onClick={() => onCloseProfileModal()}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 animate-fade-in" />

      {/* Dialog: bottom sheet on mobile, centered card on desktop */}
      <div
        className="relative z-10 w-full sm:max-w-md sm:mx-4 bg-white dark:bg-stone-800 sm:rounded-xl rounded-t-2xl shadow-xl border border-gray-200 dark:border-stone-700 overflow-hidden max-h-[90vh] max-h-[90dvh] flex flex-col animate-slide-up-sheet sm:animate-in sm:fade-in sm:zoom-in-95 sm:duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Mobile drag handle */}
        <div className="sm:hidden flex justify-center pt-3 pb-1">
          <div className="w-9 h-1 bg-gray-300 dark:bg-stone-600 rounded-full" />
        </div>

        {/* Modal Header */}
        <div className="px-4 sm:px-5 py-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-gray-900 dark:text-stone-100">
            {t("profile.title")}
          </h3>
          <button
            onClick={onCloseProfileModal}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-stone-700 transition-colors"
          >
            <X size={18} className="text-gray-500 dark:text-stone-400" />
          </button>
        </div>

        {/* Tabs - scrollable on mobile */}
        <div className="px-4 sm:px-5 border-b border-gray-100 dark:border-stone-700/80">
          <div className="flex gap-4 overflow-x-auto scrollbar-none -mb-px">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`relative flex-shrink-0 px-1 py-2.5 text-xs font-medium transition-colors whitespace-nowrap ${
                  activeTab === tab.key
                    ? "text-amber-600 dark:text-amber-400"
                    : "text-gray-500 dark:text-stone-400 hover:text-gray-700 dark:hover:text-stone-200"
                }`}
              >
                {tab.label}
                {activeTab === tab.key && (
                  <span className="absolute bottom-0 left-1 right-1 h-0.5 bg-amber-500 dark:bg-amber-400 rounded-full" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Modal Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5">
          {activeTab === "info" && (
            <>
              {/* Avatar */}
              <div className="flex flex-col items-center mb-6">
                <div className="relative">
                  {userData?.avatar_url && !imgError ? (
                    <img
                      src={userData.avatar_url}
                      alt="Avatar"
                      className="w-20 h-20 rounded-full object-cover border-4 border-white dark:border-stone-700 shadow-lg ring-2 ring-gray-100 dark:ring-stone-600"
                      onError={() => setImgError(true)}
                    />
                  ) : (
                    <div className="w-20 h-20 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center border-4 border-white dark:border-stone-700 shadow-lg ring-2 ring-gray-100 dark:ring-stone-600">
                      <span className="text-2xl font-bold text-white">
                        {userData?.username?.charAt(0).toUpperCase() || "U"}
                      </span>
                    </div>
                  )}
                  {isUploading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-full backdrop-blur-sm">
                      <Loader2 size={24} className="animate-spin text-white" />
                    </div>
                  )}
                </div>
                {canUploadAvatar && (
                  <div className="mt-3 flex items-center gap-2">
                    <label className="cursor-pointer rounded-lg bg-stone-100 dark:bg-stone-700 px-3 py-1.5 text-xs font-medium text-stone-600 dark:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-600 transition-colors">
                      {t("profile.changeAvatar")}
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        disabled={isUploading}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) handleAvatarUpload(file);
                        }}
                      />
                    </label>
                    {userData?.avatar_url && (
                      <button
                        onClick={handleAvatarDelete}
                        disabled={isUploading}
                        className="rounded-lg bg-red-50 dark:bg-red-900/30 px-3 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors disabled:opacity-50"
                      >
                        {t("profile.deleteAvatar")}
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* User Info */}
              <div className="space-y-0">
                {/* Username - editable */}
                <div className="py-3.5 border-b border-gray-100 dark:border-stone-700/60">
                  {isEditingUsername ? (
                    <div className="space-y-2">
                      <input
                        type="text"
                        value={newUsername}
                        onChange={(e) => setNewUsername(e.target.value)}
                        className="w-full rounded-lg border border-gray-300 dark:border-stone-600 bg-gray-50 dark:bg-stone-900 px-3 py-2.5 text-sm text-gray-900 dark:text-stone-100 placeholder-gray-400 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                        minLength={3}
                        maxLength={50}
                        placeholder="Enter new username"
                        autoFocus
                      />
                      {usernameError && (
                        <p className="text-xs text-red-500 dark:text-red-400">
                          {usernameError}
                        </p>
                      )}
                      <div className="flex gap-2">
                        <button
                          onClick={handleUsernameUpdate}
                          disabled={
                            isUpdatingUsername ||
                            newUsername === userData?.username
                          }
                          className="flex-1 sm:flex-none px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
                        >
                          {isUpdatingUsername ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : (
                            <Check size={14} />
                          )}
                          {t("common.save")}
                        </button>
                        <button
                          onClick={() => {
                            setIsEditingUsername(false);
                            setNewUsername("");
                            setUsernameError("");
                          }}
                          className="flex-1 sm:flex-none px-4 py-2 border border-gray-200 dark:border-stone-600 text-gray-600 dark:text-stone-400 text-sm font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-stone-700 transition-colors"
                        >
                          {t("common.cancel")}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm text-gray-500 dark:text-stone-400 shrink-0">
                        {t("profile.username")}
                      </span>
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-medium text-gray-900 dark:text-stone-100 truncate">
                          {userData?.username || "-"}
                        </span>
                        <button
                          onClick={() => {
                            setNewUsername(userData?.username || "");
                            setIsEditingUsername(true);
                          }}
                          className="shrink-0 text-amber-500 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/30 rounded-md p-1 transition-colors"
                          title={t("common.edit")}
                        >
                          <Pencil size={13} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between py-3.5 border-b border-gray-100 dark:border-stone-700/60 gap-3">
                  <span className="text-sm text-gray-500 dark:text-stone-400 shrink-0">
                    {t("profile.email")}
                  </span>
                  <span className="text-sm font-medium text-gray-900 dark:text-stone-100 truncate text-right">
                    {userData?.email || "-"}
                  </span>
                </div>
                {userData?.roles && userData.roles.length > 0 && (
                  <div className="flex items-center justify-between py-3.5 gap-3">
                    <span className="text-sm text-gray-500 dark:text-stone-400 shrink-0">
                      {t("profile.roles")}
                    </span>
                    <div className="flex flex-wrap justify-end gap-1.5">
                      {userData.roles.map((role) => (
                        <span
                          key={role}
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-300"
                        >
                          {role}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

          {activeTab === "password" && (
            <div className="space-y-4">
              {passwordSuccess && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400 text-sm">
                  <Check size={16} className="shrink-0" />
                  {t("profile.passwordChanged")}
                </div>
              )}

              {passwordError && (
                <div className="flex items-center gap-2 p-3 rounded-xl bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-sm">
                  <AlertCircle size={16} className="shrink-0" />
                  {passwordError}
                </div>
              )}

              {/* Old Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-stone-300 mb-1.5">
                  {t("profile.oldPassword")}
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={oldPassword}
                    onChange={(e) => setOldPassword(e.target.value)}
                    className="w-full px-3.5 py-2.5 pr-10 rounded-lg border border-gray-300 dark:border-stone-600 bg-white dark:bg-stone-700 text-gray-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 text-sm"
                    placeholder={t("profile.oldPassword")}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-stone-300 transition-colors"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              {/* New Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-stone-300 mb-1.5">
                  {t("profile.newPassword")}
                </label>
                <input
                  type={showPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 dark:border-stone-600 bg-white dark:bg-stone-700 text-gray-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 text-sm"
                  placeholder={t("profile.newPassword")}
                />
              </div>

              {/* Confirm Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-stone-300 mb-1.5">
                  {t("profile.confirmPassword")}
                </label>
                <input
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 dark:border-stone-600 bg-white dark:bg-stone-700 text-gray-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 text-sm"
                  placeholder={t("profile.confirmPassword")}
                />
              </div>

              {/* Submit Button */}
              <button
                onClick={handlePasswordChange}
                disabled={isLoading}
                className="w-full py-2.5 px-4 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 dark:disabled:bg-amber-700 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2 text-sm"
              >
                {isLoading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    {t("common.loading")}
                  </>
                ) : (
                  t("profile.changePassword")
                )}
              </button>
            </div>
          )}

          {activeTab === "notification" && (
            <div className="space-y-3">
              {/* Browser Notification Setting */}
              <div className="rounded-xl bg-gray-50 dark:bg-stone-700/50 p-3.5 sm:p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h4 className="font-medium text-sm text-gray-900 dark:text-stone-100">
                      {t("profile.browserNotification")}
                    </h4>
                    <p className="text-xs text-gray-500 dark:text-stone-400 mt-1 leading-relaxed">
                      {t("profile.browserNotificationDesc")}
                    </p>
                  </div>
                  {!isSupported ? (
                    <span className="shrink-0 text-xs text-gray-400 mt-0.5">
                      {t("profile.notSupported")}
                    </span>
                  ) : permission === "granted" ? (
                    <span className="shrink-0 text-xs text-green-600 dark:text-green-400 flex items-center gap-1 mt-0.5">
                      <Check size={14} />
                      {t("profile.enabled")}
                    </span>
                  ) : (
                    <button
                      onClick={requestPermission}
                      className="shrink-0 px-3 py-1.5 text-xs bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition-colors font-medium"
                    >
                      {permission === "denied"
                        ? t("profile.retry")
                        : t("profile.enable")}
                    </button>
                  )}
                </div>

                {permission === "denied" && (
                  <p className="text-xs text-red-500 mt-2.5 flex items-start gap-1.5">
                    <AlertCircle size={12} className="shrink-0 mt-0.5" />
                    {t("profile.notificationDeniedHint")}
                  </p>
                )}
              </div>

              {/* Mobile Notification Status */}
              {isMobile && (
                <div className="rounded-xl bg-gray-50 dark:bg-stone-700/50 p-3.5 sm:p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h4 className="font-medium text-sm text-gray-900 dark:text-stone-100">
                        {t("profile.mobileNotification")}
                      </h4>
                      <p className="text-xs text-gray-500 dark:text-stone-400 mt-1 leading-relaxed">
                        {t("profile.mobileNotificationDesc")}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 text-xs flex items-center gap-1 mt-0.5 ${
                        isMobileNotificationSupported()
                          ? "text-green-600 dark:text-green-400"
                          : "text-amber-600 dark:text-amber-400"
                      }`}
                    >
                      {isMobileNotificationSupported() ? (
                        <>
                          <Check size={14} />
                          {t("profile.supported")}
                        </>
                      ) : (
                        t("profile.limitedSupport")
                      )}
                    </span>
                  </div>
                </div>
              )}

              {/* WebSocket Connection Status */}
              <div className="rounded-xl bg-gray-50 dark:bg-stone-700/50 p-3.5 sm:p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h4 className="font-medium text-sm text-gray-900 dark:text-stone-100">
                      {t("profile.realtimeNotification")}
                    </h4>
                    <p className="text-xs text-gray-500 dark:text-stone-400 mt-1 leading-relaxed">
                      {t("profile.realtimeNotificationDesc")}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "agent" && <UserAgentPreferencePanel />}
        </div>

        {/* Modal Footer */}
        <div className="px-4 sm:px-5 py-3 border-t border-gray-100 dark:border-stone-700/60 flex items-center justify-between safe-area-bottom">
          <div className="text-xs text-gray-400 dark:text-stone-500">
            <span className="font-semibold text-gray-500 dark:text-stone-400 font-serif">
              LambChat
            </span>
            {versionInfo?.app_version && (
              <span className="ml-1.5">v{versionInfo.app_version}</span>
            )}
          </div>
          <button
            onClick={onCloseProfileModal}
            className="text-xs text-gray-400 dark:text-stone-500 hover:text-gray-600 dark:hover:text-stone-300 transition-colors"
          >
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/**
 * 用户默认 Agent 设置组件
 */
function UserAgentPreferencePanel() {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [availableAgents, setAvailableAgents] = useState<AgentInfo[]>([]);
  const [currentPreference, setCurrentPreference] = useState<string | null>(
    null,
  );
  const [selectedAgent, setSelectedAgent] = useState<string>("");

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [agentsRes, preferenceRes] = await Promise.all([
        agentApi.list(),
        agentConfigApi
          .getUserPreference()
          .catch(() => ({ default_agent_id: null })),
      ]);

      setAvailableAgents(agentsRes.agents || []);
      setCurrentPreference(preferenceRes.default_agent_id);
      setSelectedAgent(
        preferenceRes.default_agent_id || agentsRes.default_agent || "",
      );
    } catch (err) {
      const errorMsg = (err as Error).message || t("agentConfig.loadFailed");
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSave = async () => {
    if (!selectedAgent) return;

    setIsSaving(true);
    try {
      await agentConfigApi.setUserPreference(selectedAgent);
      setCurrentPreference(selectedAgent);
      toast.success(t("agentConfig.preferenceSaved"));
      window.dispatchEvent(new CustomEvent("agent-preference-updated"));
    } catch (err) {
      toast.error((err as Error).message || t("agentConfig.saveFailed"));
    } finally {
      setIsSaving(false);
    }
  };

  const hasChanges = selectedAgent !== currentPreference;

  if (isLoading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-sm">
          <AlertCircle size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="rounded-xl bg-gray-50 dark:bg-stone-700/50 p-3 sm:p-4">
        {availableAgents.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-stone-400 py-2">
            {t("agentConfig.noAvailableAgents")}
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {availableAgents.map((agent) => (
              <label
                key={agent.id}
                className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-3 transition-colors ${
                  selectedAgent === agent.id
                    ? "border-amber-400/60 bg-amber-50/70 dark:border-amber-500/30 dark:bg-amber-900/15"
                    : "border-transparent bg-white/60 dark:bg-stone-600/40 hover:bg-white dark:hover:bg-stone-600/70"
                }`}
              >
                <input
                  type="radio"
                  name="defaultAgent"
                  value={agent.id}
                  checked={selectedAgent === agent.id}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  className="h-4 w-4 shrink-0 border-stone-300 text-amber-500 focus:ring-amber-500/30 dark:border-stone-500 dark:text-amber-400"
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-gray-900 dark:text-stone-100 truncate">
                    {t(agent.name)}
                  </span>
                  <span className="block text-xs text-gray-500 dark:text-stone-400 mt-0.5 truncate">
                    {t(agent.description)}
                  </span>
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      {hasChanges && (
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={isSaving || !selectedAgent}
            className="px-4 py-2 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-300 dark:disabled:bg-amber-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2 text-sm"
          >
            {isSaving ? (
              <>
                <LoadingSpinner size="sm" />
                {t("common.saving")}
              </>
            ) : (
              <>
                <Save size={15} />
                {t("common.save")}
              </>
            )}
          </button>
        </div>
      )}

      {currentPreference && !hasChanges && (
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-stone-400">
          <Check
            size={16}
            className="text-green-500 dark:text-green-400 shrink-0"
          />
          <span className="truncate">
            {t("agentConfig.currentPreference", {
              agentName: t(
                availableAgents.find((a) => a.id === currentPreference)?.name ||
                  currentPreference,
              ),
            })}
          </span>
        </div>
      )}
    </div>
  );
}
