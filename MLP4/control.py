import os
import pandas as pd
import numpy as np
from subject import Subject
from gp import GP
from scipy.interpolate import interp1d
from matplotlib import pyplot as plt
from scipy.integrate import solve_ivp
from scipy.signal import savgol_filter

def calculate_contour_error(X_actual, y_actual, X_pred, y_pred, predict_start, predict_end, num_points=500):
    if predict_start >= predict_end:
        return 0
    mse = np.mean(np.square((y_actual - y_pred[:len(y_actual)])))
    return mse

def gradient_descent_algorithm(learning_rate, num_iterations, data, gp):
    print_result = 0
    epsilon = 0.005
    scale_x = 1.0
    scale_y = 1.0
    X_actual, y_actual = data
    X_scalar_end = X_actual[-1]
    y_end = y_actual[-1]
    predict_start = X_actual[0]
    predict_end = X_scalar_end

    scales_history = []
    for i in range(num_iterations):
        X_scalar_pred_new, y_pred_new = gp.scale(scale_x, scale_y, predict_end, y_end)
        contour_error = calculate_contour_error(X_actual, y_actual, X_scalar_pred_new, y_pred_new, predict_start=predict_start, predict_end=predict_end)
        scales_history.append((scale_x, scale_y, contour_error))

        #if print_result % 50 == 0:
        #    print(f"Iteration {i}: Contour Error = {contour_error}, Scale_X = {scale_x}, Scale_Y = {scale_y}")
    
        X_scalar_pred_new, y_pred_new = gp.scale(scale_x + epsilon, scale_y, X_scalar_end, y_end)
        error_x_plus = calculate_contour_error(X_actual, y_actual, X_scalar_pred_new, y_pred_new, predict_start=predict_start, predict_end=predict_end)
        X_scalar_pred_new, y_pred_new = gp.scale(scale_x - epsilon, scale_y, X_scalar_end, y_end)
        error_x_minus = calculate_contour_error(X_actual, y_actual, X_scalar_pred_new, y_pred_new, predict_start=predict_start, predict_end=predict_end)
        gradient_x = (error_x_plus - error_x_minus) / (2 * epsilon)

        X_scalar_pred_new, y_pred_new = gp.scale(scale_x, scale_y + epsilon, X_scalar_end, y_end)
        error_y_plus = calculate_contour_error(X_actual, y_actual, X_scalar_pred_new, y_pred_new, predict_start=predict_start, predict_end=predict_end)
        X_scalar_pred_new, y_pred_new = gp.scale(scale_x, scale_y - epsilon, X_scalar_end, y_end)
        error_y_minus = calculate_contour_error(X_actual, y_actual, X_scalar_pred_new, y_pred_new, predict_start=predict_start, predict_end=predict_end)
        gradient_y = (error_y_plus - error_y_minus) / (2 * epsilon)

        scale_x -= learning_rate * gradient_x
        scale_y -= learning_rate * gradient_y
        print_result +=1

    return scale_x, scale_y, scales_history



def dynamics(t, y, torque_input, subject):
    theta, omega = y
    alpha = subject.move(torque_input)[0]
    return [omega, alpha]


subject_original = Subject(6, cut=True)
subject = Subject(6, cut=True)
random_test_num = subject_original.get_random_test_num()
random_test_num=0
original_datas = subject_original.datas
gp = GP(original_datas)
interval = 20
corrected_datas ={}
corrected_datas =[]

idx = 0
t = original_datas['header'][0]
dt = original_datas['header'][1] - t
initial_t = t
heelstrike = original_datas['heelstrike'][0]
data_window = []
first_time = True
error = 0
Kp = 0
tmp = 0
idx_contrl_start=0
test=0

collect_num = 1 * 200

while idx < len(original_datas['header'])-1:

    if idx <= collect_num:
        data_point = {
            'header': original_datas['header'][idx],
            'hip_sagittal': original_datas['hip_sagittal'][idx],
            'hip_sagittal_speed': original_datas['hip_sagittal_speed'][idx],
            'hip_sagittal_acc': original_datas['hip_sagittal_acc'][idx],
            'heelstrike': original_datas['heelstrike'][idx],
            'heelstrike_x': original_datas['heelstrike_x'][idx],
            'heelstrike_y': original_datas['heelstrike_y'][idx],
            'torque': original_datas['torque'][idx]
        }
        corrected_datas[idx] = data_point
        test+=1
    else:
        if first_time:
            print('not now')
            idx_contrl_start = idx
            corrected_datas[idx] = data_point
            first_time = False
        idxc = idx - 1
        current_prediction = gp.find_pred_value_by_scalar(corrected_datas[idxc]['heelstrike'])
        print(test, idx, len(corrected_datas))
        print(test, original_datas['heelstrike'][idx - 5: idx+5], original_datas['heelstrike'][idx], corrected_datas[idxc]['heelstrike'])
        gp.translation(delx=0, dely=current_prediction - original_datas['hip_sagittal'][idx])
        data_gd = ([corrected_datas[i]['heelstrike'] for i in range(idxc)],
                   [corrected_datas[i]['hip_sagittal'] for i in range(idxc)])
        scale_x, scale_y, scales_history = gradient_descent_algorithm(0.001, 500, data_gd, gp)
        #plt.plot(gp.X_scalar, gp.y_pred, 'g', label='gp before')
        X_scalar_gp, y_pred_gp = gp.scale(scale_x, scale_y, corrected_datas[idxc]['heelstrike'], corrected_datas[idxc]['hip_sagittal'])
        print(f"idx: {idx}, scale_x: {scale_x}, scale_y: {scale_y}")
        #plt.plot(gp.X_scalar, gp.y_pred, 'b', label='gp after scale')
        #plt.plot([corrected_datas[i]['heelstrike'] for i in range(idx)], [corrected_datas[i]['hip_sagittal'] for i in range(idx)], 'r.', label='subject trajectory')
        #plt.axvline(original_datas['heelstrike'][idx])
        #plt.legend()
        #plt.show()
        torque_gp = subject.calc_torque(y_pred_gp)
        #torque_subject = corrected_datas[idx]['torque']
        torque_subject = original_datas['torque'][idx]

        # plt.plot(gp.X_scalar, torque_gp, label='gp torque')
        # plt.plot([corrected_datas[i]['heelstrike'] for i in range(idx)], [corrected_datas[i]['torque'] for i in range(idx)], 'r', label='subject torque')
        # plt.legend()
        # plt.show()
        error = y_pred_gp[idx] - corrected_datas[idxc]['hip_sagittal']
        tmp = corrected_datas[idxc]['hip_sagittal']
        tmp2 = original_datas['hip_sagittal'][idx]
        print(original_datas['hip_sagittal'][idx-5:idx+5])
        print(f'angle / gp: {y_pred_gp[idx]}, subject: {tmp}, original: {tmp2} e: {error}')
        torque_input = Kp * error + torque_subject # torque_gp[-1]
        print('torque / gp: ', torque_gp[-1], 'original', original_datas['torque'][idx], 'subject: ', torque_subject, 'input: ', torque_input)
    

        a_t = subject.move(torque_input)[0]
        print(a_t, original_datas['hip_sagittal_acc'][idx])
        #x_t = corrected_datas[idxc-1]['hip_sagittal'] + corrected_datas[idxc-1]['hip_sagittal_speed'] * dt
        #v_t = corrected_datas[idxc-1]['hip_sagittal_speed'] + corrected_datas[idxc-1]['hip_sagittal_acc'] * dt
        ddt = dt * 0.1
        a_dt = a_t - corrected_datas[idxc]['hip_sagittal_acc']
        x_t = corrected_datas[idxc]['hip_sagittal']
        v_t = corrected_datas[idxc]['hip_sagittal_speed']
        print(f"before: {idx}, x_t: {x_t}, v_t: {v_t}")
        for _ in range(10):
            x_t1 = x_t + v_t * ddt
            v_t1 = v_t + a_t * ddt
            a_t1 = a_t + a_dt * ddt
            x_t = x_t1
            v_t = v_t1
            a_t = a_t1
        print(f"after: {idx}, x_t: {x_t}, v_t: {v_t}")
        print(f"wanted after: {idx}, x_t: {original_datas['hip_sagittal'][idx+1]}, v_t: {original_datas['hip_sagittal_speed'][idx+1]}")

        data_point = {
            'header': original_datas['header'][idx+1],
            'hip_sagittal': x_t1,
            'hip_sagittal_speed': v_t1,
            'hip_sagittal_acc': a_t1, #corrected_datas[idx]['hip_sagittal_acc'],
            'heelstrike': original_datas['heelstrike'][idx+1],
            'heelstrike_x': original_datas['heelstrike_x'][idx+1],
            'heelstrike_y': original_datas['heelstrike_y'][idx+1],
            'torque': torque_input
        }
        corrected_datas[idxc+1] = data_point

    t += 0.005
    idx += 1
    if t >= 30:
        break

plt.plot(original_datas['heelstrike'], original_datas['hip_sagittal'], label='original trajectory')
plt.plot([corrected_datas[i]['heelstrike'] for i in range(idx)], [corrected_datas[i]['hip_sagittal'] for i in range(idx)], 'r', label='corrected trajectory')
dely = gp.y_pred[idx_contrl_start] - original_datas['hip_sagittal'][idx_contrl_start]
gp.translation(dely=dely)
plt.plot(gp.X_scalar, gp.y_pred, 'b', label='gp data')
plt.axvline(original_datas['heelstrike'][idx_contrl_start-1])
plt.legend()
plt.show()